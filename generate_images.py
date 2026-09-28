"""
Módulo de Generación de Imágenes Conceptuales (Estilo C) con Motor Híbrido (Gemini + Fallback OpenAI DALL-E 3).
Segmenta el audio maestro en intervalos aleatorios de 13 a 18 segundos y genera una imagen única y sincronizada para cada intervalo.
"""

import os
import sys
import json
import time
import random
import re
import urllib.request
import argparse
from pathlib import Path

# Compatibilidad UTF-8 para Windows
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

OUTPUTS_DIR = Path("outputs")
IMAGENES_DIR = OUTPUTS_DIR / "imagenes"
AUDIO_PATH = OUTPUTS_DIR / "audio_maestro.mp3"
GUION_PATH = OUTPUTS_DIR / "guion_final.md"
TIMELINE_FILE = OUTPUTS_DIR / "scenes_timeline.json"

# Configuración de estilos y motores
# Estilo Animado / Ilustración 2D Vectorial Limpia
STYLE_ANIMATED_VECTOR_SUFFIX = (
    "modern 2D vector animation illustration style, clean flat graphic art, vibrant harmonious color palette, "
    "crisp geometric shapes, minimalist aesthetic, beautiful clean lighting, 16:9 widescreen composition, "
    "no text, no watermark, no realistic photo texture, no photorealism"
)

DEFAULT_GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002")


def get_audio_duration_seconds() -> float:
    """Calcula la duración exacta del audio maestro en segundos."""
    if not AUDIO_PATH.exists():
        # Fallback a la duración indicada por el usuario: 17:08 = 1028s
        return 1028.0

    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(AUDIO_PATH))
        return len(audio) / 1000.0
    except Exception:
        pass

    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(str(AUDIO_PATH))
        dur = clip.duration
        clip.close()
        return float(dur)
    except Exception:
        pass

    return 1028.0


def extract_script_sections(guion_path: Path) -> list[str]:
    """Extrae párrafos de narración útiles del guion para contextualizar las imágenes."""
    if not guion_path.exists():
        return ["Evergreen habits and sustainable life principles for personal clarity and focus."]

    with open(guion_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    paragraphs = []
    current_block = []

    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#") or clean.startswith("---") or clean.startswith(">"):
            if current_block:
                text = " ".join(current_block)
                if len(text) > 30:
                    paragraphs.append(text)
                current_block = []
            continue

        if clean.startswith("[") and clean.endswith("]"):
            continue

        # Limpiar etiquetas
        clean = re.sub(r"^\*\*(?:VOZ EN OFF|NARRADOR|INDICACIÓN VISUAL)[\:\*]*\s*", "", clean, flags=re.IGNORECASE)
        clean = clean.strip("*_`[]")
        if clean:
            current_block.append(clean)

    if current_block:
        text = " ".join(current_block)
        if len(text) > 30:
            paragraphs.append(text)

    return paragraphs if paragraphs else ["Evergreen habits for mental clarity and productivity."]


def build_timeline(total_duration: float, script_paragraphs: list[str]) -> list[dict]:
    """
    Divide el tiempo total en segmentos de 13 a 18 segundos y asigna el contexto narrativo y prompt.
    """
    random.seed(42)  # Semilla reproducible para mantener la misma estructura
    segments = []
    current_time = 0.0
    idx = 0

    while current_time < total_duration:
        remaining = total_duration - current_time
        if remaining <= 18.0:
            dur = remaining
        else:
            dur = random.uniform(13.0, 18.0)
            if (remaining - dur) < 13.0:
                # Si el remanente quedara muy pequeño, dividimos en 2 partes iguales
                dur = remaining / 2.0

        p_idx = min(int((current_time / total_duration) * len(script_paragraphs)), len(script_paragraphs) - 1)
        narrative_snippet = script_paragraphs[p_idx]

        # Sintetizar un prompt visual en inglés basado en el fragmento
        # Limpiar texto para prompting
        snippet_clean = re.sub(r"[^\w\s\.,]", "", narrative_snippet)[:120]

        prompt_scene = f"A modern 2D vector animation illustration of: {snippet_clean}. {STYLE_ANIMATED_VECTOR_SUFFIX}"

        segments.append({
            "index": idx,
            "start_time": round(current_time, 2),
            "duration": round(dur, 2),
            "end_time": round(current_time + dur, 2),
            "narrative_context": narrative_snippet[:160],
            "prompt": prompt_scene,
            "image_file": f"escena_{idx:03d}.png",
            "completed": False,
            "engine_used": None
        })

        current_time += dur
        idx += 1

    return segments


def load_or_create_timeline(total_duration: float, script_paragraphs: list[str]) -> list[dict]:
    """Carga la línea temporal existente o genera una nueva."""
    if TIMELINE_FILE.exists():
        try:
            with open(TIMELINE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                # Verificar imágenes que ya existen físicamente
                for item in data:
                    img_p = IMAGENES_DIR / item["image_file"]
                    if img_p.exists() and img_p.stat().st_size > 1000:
                        item["completed"] = True
                return data
        except Exception:
            pass

    timeline = build_timeline(total_duration, script_paragraphs)
    save_timeline(timeline)
    return timeline


def save_timeline(timeline: list[dict]):
    """Guarda el estado de la línea temporal de forma segura."""
    TIMELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_f = TIMELINE_FILE.with_suffix(".json.tmp")
    with open(temp_f, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temp_f.replace(TIMELINE_FILE)


# ==============================================================================
# MOTORES DE GENERACIÓN DE IMAGEN
# ==============================================================================
# Estado de disponibilidad de motores en la sesión actual
GEMINI_ENABLED = True
DALLE_ENABLED = True


def generate_image_gemini(prompt: str, output_path: Path) -> bool:
    """Intenta generar la imagen usando Google Gemini / Imagen."""
    global GEMINI_ENABLED
    if not GEMINI_ENABLED:
        return False

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        GEMINI_ENABLED = False
        return False

    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)

        result = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt
        )
        if result and result.candidates and result.candidates[0].content and result.candidates[0].content.parts:
            for part in result.candidates[0].content.parts:
                if getattr(part, 'inline_data', None) and part.inline_data.data:
                    import base64
                    data = part.inline_data.data
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    with open(output_path, "wb") as f:
                        f.write(data)
                    return True
    except Exception as e:
        err_msg = str(e).lower()
        if "429" in err_msg or "quota" in err_msg or "resource_exhausted" in err_msg or "not_found" in err_msg or "404" in err_msg:
            print("⚠️ Gemini no admite generación de imagen en este tier (cuota 0). Desactivando Tier 1 para esta sesión.")
            GEMINI_ENABLED = False
            return False

    return False


def generate_image_dalle(prompt: str, output_path: Path) -> bool:
    """Genera la imagen usando OpenAI DALL-E como fallback."""
    global DALLE_ENABLED
    if not DALLE_ENABLED:
        return False

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        DALLE_ENABLED = False
        return False

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt[:900],
            size="1792x1024",
            quality="standard",
            n=1
        )
        if response and response.data and response.data[0].url:
            urllib.request.urlretrieve(response.data[0].url, str(output_path))
            return output_path.exists() and output_path.stat().st_size > 1000

    except Exception as e:
        err_msg = str(e).lower()
        if "does not exist" in err_msg or "400" in err_msg or "429" in err_msg or "permission" in err_msg:
            print(f"⚠️ OpenAI DALL-E no habilitado en esta clave ({e}). Desactivando Tier 2 para esta sesión.")
            DALLE_ENABLED = False
            return False

    return False


def generate_image_flux(prompt: str, output_path: Path, scene_index: int = 0) -> bool:
    """Generador FLUX 16:9 con reintentos robustos y backoff exponencial."""
    import urllib.parse

    # Prompt más corto para evitar problemas de URL larga
    clean_prompt = prompt[:280]
    encoded = urllib.parse.quote(clean_prompt)
    seed = (scene_index * 1337 + 42) % 100000

    MAX_RETRIES = 4
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            url = f"https://image.pollinations.ai/prompt/{encoded}?width=1280&height=720&nologo=true&seed={seed}&model=flux"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()

            # Validar que no sea un JSON de error de Pollinations
            if len(data) < 2000:
                try:
                    text = data.decode("utf-8", errors="ignore")
                    if '"error"' in text or '"Too Many Requests"' in text:
                        wait = 2 ** attempt + random.uniform(0, 2)
                        print(f"   ⏳ Pollinations ocupado (intento {attempt}/{MAX_RETRIES}), reintentando en {wait:.0f}s...")
                        time.sleep(wait)
                        seed += 1  # Cambiar seed para evitar caché de error
                        continue
                except Exception:
                    pass

            with open(output_path, "wb") as f:
                f.write(data)

            if output_path.exists() and output_path.stat().st_size > 2000:
                return True
            else:
                print(f"   ⚠️ Imagen muy pequeña ({len(data)} bytes), reintentando...")

        except Exception as e:
            err_msg = str(e)
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt + random.uniform(0, 2)
                print(f"   ⏳ Error FLUX ({err_msg}), reintento {attempt}/{MAX_RETRIES} en {wait:.0f}s...")
                time.sleep(wait)
                seed += 1
            else:
                print(f"   ❌ Error FLUX tras {MAX_RETRIES} intentos: {err_msg}")
                return False

    return False



def generate_single_image(prompt: str, output_path: Path, preferred_engine: str = "flux", scene_index: int = 0) -> tuple[bool, str]:
    """
    Genera la imagen con arquitectura de 3 niveles.
    En modo 'auto': FLUX (primario) -> Gemini -> DALL-E (fallback).
    """
    temp_path = output_path.with_suffix(".png.tmp")

    # --- Motor específico seleccionado ---
    if preferred_engine == "flux":
        print("🎨 Renderizando con motor FLUX Ilustración 2D 16:9...")
        if generate_image_flux(prompt, temp_path, scene_index=scene_index):
            temp_path.replace(output_path)
            return True, "FLUX Ilustración 2D"
        return False, "failed"

    if preferred_engine == "dalle" and DALLE_ENABLED:
        if generate_image_dalle(prompt, temp_path):
            temp_path.replace(output_path)
            return True, "OpenAI DALL-E"
        return False, "failed"

    if preferred_engine == "gemini" and GEMINI_ENABLED:
        print("🎨 Consultando Google Gemini...")
        if generate_image_gemini(prompt, temp_path):
            temp_path.replace(output_path)
            return True, "Google Gemini"
        return False, "failed"

    # --- Modo AUTO: FLUX primero (más confiable), luego Gemini, luego DALL-E ---
    print("🎨 [Motor Principal] Renderizando con FLUX Ilustración 2D 16:9...")
    if generate_image_flux(prompt, temp_path, scene_index=scene_index):
        temp_path.replace(output_path)
        return True, "FLUX Ilustración 2D"

    if GEMINI_ENABLED:
        print("🎨 [Fallback 1] Consultando Google Gemini...")
        if generate_image_gemini(prompt, temp_path):
            temp_path.replace(output_path)
            return True, "Google Gemini"

    if DALLE_ENABLED:
        print("🎨 [Fallback 2] Conmutando a OpenAI DALL-E...")
        if generate_image_dalle(prompt, temp_path):
            temp_path.replace(output_path)
            return True, "OpenAI DALL-E"

    return False, "failed"


# ==============================================================================
# FLUJO PRINCIPAL
# ==============================================================================
def main():
    default_engine = os.getenv("IMAGE_ENGINE", "flux").strip().lower()
    parser = argparse.ArgumentParser(description="Generador de Ilustraciones Animadas 2D BMAD (Vectorial / Flat Animation)")
    parser.add_argument("--max-images", type=int, default=None, help="Límite de imágenes a generar en esta ejecución")
    parser.add_argument("--engine", choices=["auto", "flux", "gemini", "dalle"], default=default_engine, help="Motor preferido")
    parser.add_argument("--reset-timeline", action="store_true", help="Regenera el mapa de tiempos desde cero")
    args = parser.parse_args()

    IMAGENES_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset_timeline and TIMELINE_FILE.exists():
        TIMELINE_FILE.unlink()
        print("🔄 Mapa de tiempos reiniciado.")

    duracion_audio = get_audio_duration_seconds()
    parrafos_guion = extract_script_sections(GUION_PATH)

    timeline = load_or_create_timeline(duracion_audio, parrafos_guion)

    print("=" * 65)
    print("🎨 GENERADOR DE ILUSTRACIONES ANIMADAS 2D (Estilo Animación Vectorial)")
    print(f"⏱️  Duración del audio detectada: {duracion_audio / 60:.2f} minutos ({duracion_audio:.1f} segundos)")
    print(f"🖼️  Total de escenas/imágenes calculadas: {len(timeline)}")
    print(f"⏱️  Duración por imagen: Aleatorio entre 13.0s y 18.0s")
    print(f"🤖 Motor: {args.engine.upper()} (Gemini ➔ DALL-E ➔ FLUX)")
    print("=" * 65)

    completadas = sum(1 for item in timeline if item.get("completed", False))
    print(f"📊 Progreso actual: {completadas}/{len(timeline)} imágenes listas en '{IMAGENES_DIR}'\n")

    procesadas_sesion = 0

    for item in timeline:
        idx = item["index"]
        output_file = IMAGENES_DIR / item["image_file"]

        if item.get("completed", False) and output_file.exists() and output_file.stat().st_size > 1000:
            continue

        if args.max_images is not None and procesadas_sesion >= args.max_images:
            print(f"\n⏹️ Se alcanzó el límite solicitado de {args.max_images} imágenes para esta sesión.")
            break

        print("──────────────────────────────────────────────────────────")
        print(f"📸 ESCENA {idx + 1}/{len(timeline)} | Tiempo: {item['start_time']}s ➔ {item['end_time']}s (Duración: {item['duration']}s)")
        print(f"📝 Contexto: \"{item['narrative_context'][:80]}...\"")
        print("──────────────────────────────────────────────────────────")

        exito, motor = generate_single_image(item["prompt"], output_file, preferred_engine=args.engine, scene_index=idx)

        if exito:
            print(f"✅ ¡Escena {idx + 1} generada con éxito con [{motor}]!")
            item["completed"] = True
            item["engine_used"] = motor
            save_timeline(timeline)
            procesadas_sesion += 1
            time.sleep(1)
        else:
            print(f"❌ No se pudo generar la imagen para la escena {idx + 1}.")
            print("🛑 Proceso en pausa. Verifica tus claves de API o conexión y reanuda cuando desees.")
            save_timeline(timeline)
            return 1

    total_completadas = sum(1 for item in timeline if item.get("completed", False))
    print("\n" + "=" * 65)
    print(f"🎉 GENERACIÓN FINALIZADA: {total_completadas}/{len(timeline)} imágenes disponibles.")
    print(f"📁 Directorio de imágenes: {IMAGENES_DIR.resolve()}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
