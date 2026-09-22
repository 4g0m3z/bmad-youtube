import os
import json
import time
import sys
import argparse
from pathlib import Path

# Asegurar compatibilidad UTF-8 en terminales Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# CONFIGURACIÓN DE RUTAS Y MODELOS
# ==============================================================================
MODEL_ID = os.getenv("VEO_MODEL_ID", "veo-3.1-generate-preview")
PROMPTS_FILE = Path("outputs/prompts_video.md")
OUTPUT_DIR = Path("outputs/videos_finales")
STATE_FILE = Path("outputs/video_generation_state.json")

# Parámetros técnicos de video
ASPECT_RATIO = os.getenv("VEO_ASPECT_RATIO", "16:9")
VIDEO_DURATION_SECONDS = int(os.getenv("VEO_DURATION_SECONDS", "5"))

# Configuración de resiliencia
MAX_RETRIES = 5
BASE_DELAY = 10
RETRYABLE_STATUS_CODES = [429, 503]


def get_genai_client():
    """Inicializa y valida el cliente de Google GenAI."""
    try:
        from google import genai
    except ImportError:
        print("❌ Error: 'google-genai' no está instalado. Ejecuta: pip install google-genai")
        sys.exit(1)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error crítico: La variable de entorno GEMINI_API_KEY no está configurada.")
        print("Defínela en tu archivo .env o en las variables de tu sistema.")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def check_available_models():
    """Consulta y lista los modelos disponibles en la API de Google GenAI."""
    client = get_genai_client()
    print("🔍 Consultando modelos disponibles en tu cuenta de Google AI Studio...")
    try:
        models = client.models.list()
        print("\n📋 Modelos encontrados:")
        found_any = False
        for m in models:
            name = getattr(m, 'name', str(m))
            display_name = getattr(m, 'display_name', '')
            supported_actions = getattr(m, 'supported_actions', [])
            print(f"  • {name} ({display_name}) - Acciones: {supported_actions}")
            found_any = True
        if not found_any:
            print("  (No se listaron modelos o la cuenta tiene restricciones)")
    except Exception as e:
        print(f"❌ Error al consultar lista de modelos: {e}")


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
                if "Google Veo Prompt:" in clean_line or "**Prompt:**" in clean_line:
                    awaiting_prompt = True
                    continue
                if awaiting_prompt and clean_line.startswith(">"):
                    prompt = clean_line[1:].strip()
                    if prompt:
                        prompts.append(prompt)
                    awaiting_prompt = False

        if not prompts:
            # Fallback: intentar extraer bloques de código o líneas de prompt numeradas
            with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extraer bloques de prompt entre comillas o líneas con formato
                import re
                matches = re.findall(r"(?:Prompt|Google Veo Prompt)[\s\:\*]+>*\s*([^\n\r]+)", content, re.IGNORECASE)
                if matches:
                    prompts = [m.strip().strip("> ") for m in matches if len(m.strip()) > 10]

        if not prompts:
            print(f"⚠️ Advertencia: El archivo '{PROMPTS_FILE}' no contiene prompts reconocibles con el formato esperado.")
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
    """Guarda el progreso actual de forma atómica."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_state_file = STATE_FILE.with_suffix('.json.tmp')
    with open(temporary_state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temporary_state_file.replace(STATE_FILE)


def video_output_path(scene_index):
    """Devuelve la ruta estable del video de una escena."""
    return OUTPUT_DIR / f"escena_{scene_index:03d}.mp4"


def is_completed_video(scene_index):
    """Comprueba que existe un MP4 completo antes de saltar una escena."""
    output_path = video_output_path(scene_index)
    # Comprobar tanto formato escena_0.mp4 como escena_000.mp4
    alt_path = OUTPUT_DIR / f"escena_{scene_index}.mp4"
    return (output_path.is_file() and output_path.stat().st_size > 0) or (alt_path.is_file() and alt_path.stat().st_size > 0)


# ==============================================================================
# LÓGICA DE LLAMADA CON RESILIENCIA
# ==============================================================================
def generate_video_with_retry(client, prompt, scene_index):
    """Ejecuta la llamada a la API implementando reintentos ante saturación y fallbacks de configuración."""
    from google.genai import types
    from google.genai.errors import APIError

    # Configuración inicial
    config_kwargs = {}
    if ASPECT_RATIO:
        config_kwargs["aspect_ratio"] = ASPECT_RATIO
    if VIDEO_DURATION_SECONDS and VIDEO_DURATION_SECONDS > 0:
        config_kwargs["duration_seconds"] = VIDEO_DURATION_SECONDS

    current_config = types.GenerateVideosConfig(**config_kwargs)

    for attempt in range(MAX_RETRIES):
        try:
            print(f"🎬 [Escena {scene_index}] Enviando a modelo '{MODEL_ID}'... (Intento {attempt + 1}/{MAX_RETRIES})")

            operation = client.models.generate_videos(
                model=MODEL_ID,
                source=types.GenerateVideosSource(prompt=prompt),
                config=current_config
            )

            print(f"⏳ [Escena {scene_index}] Procesando en Google (Operación: {operation.name})...")

            while not operation.done:
                time.sleep(15)
                operation = client.operations.get(operation)

            result = operation.result
            if result and result.generated_videos:
                return result.generated_videos[0]
            else:
                raise Exception("La operación finalizó pero no devolvió bytes de video válidos.")

        except APIError as e:
            print(f"⚠️ [API Error - Escena {scene_index}]: Código {e.code} - {e.message}")

            # Si la API rechaza el valor explícito de duration_seconds, reintentar con el default nativo
            if e.code == 400 and "durationSeconds" in str(e.message):
                print(f"🔄 Reintentando con la duración predeterminada nativa del modelo '{MODEL_ID}'...")
                current_config = types.GenerateVideosConfig(aspect_ratio=ASPECT_RATIO)
                time.sleep(2)
                continue

            if e.code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"⏳ Servidor ocupado o cuota temporal. Esperando {delay}s antes de reintentar...")
                time.sleep(delay)
            else:
                if e.code == 404:
                    raise RuntimeError(
                        f"El modelo '{MODEL_ID}' no está disponible o no admite generación de video en este proyecto. "
                        "Ejecuta con --check-models para ver los modelos habilitados en tu cuenta."
                    ) from e
                raise RuntimeError(
                    f"Error de Google (código {e.code}): {e.message}"
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
    parser = argparse.ArgumentParser(description="Generador de clips de video con Google Veo")
    parser.add_argument("--check-models", action="store_true", help="Lista los modelos disponibles en tu API key")
    parser.add_argument("--max-scenes", type=int, default=None, help="Límite de escenas a procesar en esta ejecución")
    parser.add_argument("--reset-state", action="store_true", help="Reinicia el registro de estado de fallos")
    args = parser.parse_args()

    if args.check_models:
        check_available_models()
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = get_genai_client()
    prompts_list = load_prompts_from_markdown()
    state = load_state()

    if args.reset_state:
        state["failed_indices"] = {}
        save_state(state)
        print("🔄 Estado de errores reiniciado.")

    print("=" * 60)
    print(f"🚀 INICIANDO GENERADOR DE VIDEO BMAD (Google Veo)")
    print(f"📂 Archivo de prompts: {PROMPTS_FILE}")
    print(f"🤖 Modelo configurado: {MODEL_ID}")
    print(f"🎬 Total de escenas detectadas: {len(prompts_list)}")
    print("=" * 60)

    completed_indices = set(state["completed_indices"])
    for index in range(len(prompts_list)):
        if is_completed_video(index):
            completed_indices.add(index)
    state["completed_indices"] = sorted(completed_indices)
    save_state(state)

    print(f"🔄 Escenas ya generadas previamente: {len(completed_indices)}/{len(prompts_list)}")

    processed_count = 0
    for index, prompt_text in enumerate(prompts_list):
        if args.max_scenes is not None and processed_count >= args.max_scenes:
            print(f"\n⏹️ Se alcanzó el límite solicitado de {args.max_scenes} escenas para esta ejecución.")
            break

        if index in completed_indices:
            continue

        print(f"\n──────────────────────────────────────────────────────────")
        print(f"🎥 PROCESANDO ESCENA {index + 1}/{len(prompts_list)}: '{prompt_text[:60]}...'")
        print(f"──────────────────────────────────────────────────────────")

        try:
            video_data = generate_video_with_retry(client, prompt_text, index)

            # Obtener bytes del video generado
            video_bytes = None
            if hasattr(video_data, 'video') and getattr(video_data.video, 'video_bytes', None):
                video_bytes = video_data.video.video_bytes
            elif hasattr(video_data, 'video') and getattr(video_data.video, 'image', None) and getattr(video_data.video.image, 'image_bytes', None):
                video_bytes = video_data.video.image.image_bytes
            elif hasattr(video_data, 'video') and hasattr(client, 'files') and getattr(video_data.video, 'name', None):
                try:
                    video_bytes = client.files.download(file=video_data.video.name)
                except Exception:
                    pass

            if not video_bytes:
                # Si video_data tiene método download o save
                if hasattr(video_data, 'video') and hasattr(video_data.video, 'download'):
                    output_path = video_output_path(index)
                    video_data.video.download(str(output_path))
                    if output_path.exists() and output_path.stat().st_size > 0:
                        video_bytes = b"downloaded"
                elif hasattr(video_data, 'video') and hasattr(video_data.video, 'save'):
                    output_path = video_output_path(index)
                    video_data.video.save(str(output_path))
                    if output_path.exists() and output_path.stat().st_size > 0:
                        video_bytes = b"saved"

            if not video_bytes:
                raise ValueError(f"La respuesta no contiene bytes de video válidos. Estructura: {type(video_data)} - {video_data}")

            output_path = video_output_path(index)
            if video_bytes not in (b"downloaded", b"saved"):
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
            processed_count += 1

        except Exception as e:
            print(f"❌ La escena {index} falló: {e}")
            state["failed_indices"][str(index)] = str(e)
            save_state(state)
            print("🛑 Proceso detenido. Corrige el problema o verifica el modelo y vuelve a ejecutar.")
            return 1

    print("\n🏁 Proceso de generación de video finalizado.")
    print(f"🎉 Escenas totales completadas: {len(state['completed_indices'])}/{len(prompts_list)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())