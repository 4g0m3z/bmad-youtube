import os
import json
import time
import sys
from pathlib import Path
from google import genai
from google.genai import types
from google.genai.errors import APIError

# ==============================================================================
# CONFIGURACIÓN DE RUTAS DEL PROYECTO
# ==============================================================================
MODEL_ID = os.getenv("VEO_MODEL_ID", "veo-3.1-fast-generate-preview")
PROMPTS_FILE = Path("outputs/prompts_video.md")
OUTPUT_DIR = Path("outputs/videos_finales")
STATE_FILE = Path("outputs/video_generation_state.json")

# Parámetros técnicos solicitados
ASPECT_RATIO = "16:9"
VIDEO_DURATION_SECONDS = 8

# Configuración de resiliencia
MAX_RETRIES = 5
BASE_DELAY = 10
RETRYABLE_STATUS_CODES = [429, 503]

# Inicializar cliente de Google GenAI
if not os.environ.get("GEMINI_API_KEY"):
    print("❌ Error crítico: La variable de entorno GEMINI_API_KEY no está configurada.")
    print("Configúrala en tu terminal de VS Code ejecutando: export GEMINI_API_KEY='tu_llave'")
    sys.exit(1)

client = genai.Client()

# Asegurar que las carpetas de salida existan
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# FUNCIONES DE PERSISTENCIA Y LECTURA DE MARKDOWN
# ==============================================================================
def load_prompts_from_markdown():
    """Lee el archivo .md y extrae cada línea válida como un prompt."""
    if not PROMPTS_FILE.exists():
        print(f"❌ Error: No se encontró el archivo de prompts en la ruta: '{PROMPTS_FILE}'")
        sys.exit(1)

    prompts = []
    awaiting_prompt = False
    try:
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                clean_line = line.strip()
                if "Google Veo Prompt:" in clean_line:
                    awaiting_prompt = True
                    continue
                if awaiting_prompt and clean_line.startswith(">"):
                    prompt = clean_line[1:].strip()
                    if prompt:
                        prompts.append(prompt)
                    awaiting_prompt = False

        if not prompts:
            print(f"⚠️ Advertencia: El archivo '{PROMPTS_FILE}' está vacío o no contiene líneas de texto válidas.")
            sys.exit(1)

        return prompts
    except Exception as e:
        print(f"❌ Error al leer el archivo Markdown: {str(e)}")
        sys.exit(1)

def load_state():
    """Carga el estado de progreso para reanudación."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            if not isinstance(state, dict):
                raise ValueError("El estado no contiene un objeto JSON.")

            completed_indices = state.get("completed_indices", [])
            failed_indices = state.get("failed_indices", {})
            if not isinstance(completed_indices, list):
                completed_indices = []
            if not isinstance(failed_indices, dict):
                failed_indices = {}

            return {
                "completed_indices": sorted({
                    int(index) for index in completed_indices
                    if isinstance(index, int) and index >= 0
                }),
                "failed_indices": failed_indices,
            }
        except Exception:
            print("⚠️ Archivo de estado corrupto. Se creará uno nuevo.")
    return {"completed_indices": [], "failed_indices": {}}

def save_state(state):
    """Guarda el progreso actual."""
    temporary_state_file = STATE_FILE.with_suffix('.json.tmp')
    with open(temporary_state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temporary_state_file.replace(STATE_FILE)

def video_output_path(scene_index):
    """Devuelve la ruta estable del video de una escena."""
    return OUTPUT_DIR / f"escena_{scene_index}.mp4"

def is_completed_video(scene_index):
    """Comprueba que existe un MP4 completo antes de saltar una escena."""
    output_path = video_output_path(scene_index)
    return output_path.is_file() and output_path.stat().st_size > 0

# ==============================================================================
# LOGICA DE LLAMADA CON RESILIENCIA
# ==============================================================================
def generate_video_with_retry(prompt, scene_index):
    """Ejecuta la llamada a la API implementando reintentos ante saturación."""
    config = types.GenerateVideosConfig(
        aspect_ratio=ASPECT_RATIO,
        duration_seconds=VIDEO_DURATION_SECONDS
    )

    for attempt in range(MAX_RETRIES):
        try:
            print(f"🎬 [Escena {scene_index}] Enviando a {MODEL_ID}... (Intento {attempt + 1}/{MAX_RETRIES})")

            operation = client.models.generate_videos(
                model=MODEL_ID,
                source=types.GenerateVideosSource(prompt=prompt),
                config=config
            )

            print(f"⏳ [Escena {scene_index}] Procesando en Google (ID: {operation.name})...")

            while not operation.done:
                time.sleep(20)
                operation = client.operations.get(operation)

            result = operation.result
            if result and result.generated_videos:
                return result.generated_videos[0]
            else:
                raise Exception("La operación finalizó pero no devolvió bytes de video válidos.")

        except APIError as e:
            print(f"⚠️ [API Error - Escena {scene_index}]: Código {e.code} - {e.message}")

            if e.code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"⏳ Servidor saturado o límite alcanzado. Esperando {delay} segundos antes de reintentar...")
                time.sleep(delay)
            else:
                if e.code == 404:
                    raise RuntimeError(
                        f"El modelo '{MODEL_ID}' no está disponible para la API "
                        "v1beta o no admite predictLongRunning en este proyecto. "
                        "Consulta client.models.list() y usa un modelo Veo "
                        "habilitado para tu cuenta."
                    ) from e
                raise RuntimeError(
                    f"Error no recuperable de Google (código {e.code}): {e.message}"
                ) from e
        except Exception as e:
            raise RuntimeError(
                f"Error durante la generación de la escena {scene_index}: {e}"
            ) from e

    raise Exception(f"Fallaron todos los {MAX_RETRIES} intentos por saturación del servicio.")

# ==============================================================================
# FLUJO PRINCIPAL
# ==============================================================================
def main():
    prompts_list = load_prompts_from_markdown()
    state = load_state()

    print(f"🚀 Iniciando script Premium.")
    print(f"📂 Archivo de origen: {PROMPTS_FILE}")
    print(f"🎬 Total de escenas detectadas en el archivo: {len(prompts_list)}")
    completed_indices = set(state["completed_indices"])
    for index in range(len(prompts_list)):
        if is_completed_video(index):
            completed_indices.add(index)
    state["completed_indices"] = sorted(completed_indices)
    save_state(state)

    print(f"🔄 Escenas ya procesadas con éxito: {len(completed_indices)}")

    for index, prompt_text in enumerate(prompts_list):
        # Evitar procesar escenas que ya se completaron de forma exitosa
        if index in completed_indices:
            continue

        print(f"\n──────────────────────────────────────────────────────────")
        print(f"🎥 PROCESANDO ESCENA {index}: '{prompt_text[:60]}...'")
        print(f"──────────────────────────────────────────────────────────")

        try:
            video_data = generate_video_with_retry(prompt_text, index)

            # Guardar el video dentro de outputs/videos_finales
            video_bytes = video_data.video.video_bytes if video_data.video else None
            if not video_bytes:
                raise ValueError("La respuesta no contiene bytes de video válidos.")

            output_path = video_output_path(index)
            temporary_output_path = output_path.with_suffix('.mp4.tmp')
            with open(temporary_output_path, "wb") as f:
                f.write(video_bytes)
                f.flush()
                os.fsync(f.fileno())
            temporary_output_path.replace(output_path)

            print(f"✅ ¡Escena {index} guardada en: {output_path}!")

            completed_indices.add(index)
            state["completed_indices"] = sorted(completed_indices)
            if str(index) in state["failed_indices"]:
                del state["failed_indices"][str(index)]
            save_state(state)

        except Exception as e:
            print(f"❌ La escena {index} falló de forma permanente en este ciclo.")
            print(f"📝 Razón explícita del fallo: {str(e)}")
            state["failed_indices"][str(index)] = str(e)
            save_state(state)
            print("🛑 Proceso detenido para no avanzar a la siguiente escena.")
            print("💾 Progreso guardado. Corrige el problema y vuelve a ejecutar el script.")
            return 1

    print("\n🏁 Proceso de renderizado por lotes finalizado.")
    print(f"🎉 Escenas totales completadas con éxito: {len(state['completed_indices'])}/{len(prompts_list)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())