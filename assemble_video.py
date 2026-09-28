"""
Módulo de Ensamblado y Renderizado Final para YouTube (BMAD Pipeline).
Une la secuencia de imágenes conceptuales aplicando el efecto Ken Burns (paneo y zoom dinámico)
y sincroniza la pista de audio maestro de 17:08 minutos con transiciones suaves.
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path
from PIL import Image
import numpy as np

# Compatibilidad UTF-8 en terminales Windows
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
TIMELINE_FILE = OUTPUTS_DIR / "scenes_timeline.json"
DEFAULT_OUTPUT_VIDEO = OUTPUTS_DIR / "video_final_youtube.mp4"


def create_ken_burns_clip(
    image_path: Path,
    duration: float,
    target_resolution: tuple[int, int] = (1920, 1080),
    fps: int = 24,
    motion_type: int = 0
):
    """
    Crea un VideoClip de MoviePy aplicando un efecto Ken Burns (Zoom/Pan suave) a una imagen estática.
    """
    from moviepy.editor import VideoClip

    # Cargar y convertir imagen base
    pil_img = Image.open(image_path).convert("RGB")
    target_w, target_h = target_resolution
    target_ratio = target_w / target_h

    # Recortar imagen base para que coincida exactamente con la relación 16:9
    img_w, img_h = pil_img.size
    img_ratio = img_w / img_h

    if img_ratio > target_ratio:
        # Imagen más ancha: recortar lados
        new_w = int(img_h * target_ratio)
        left = (img_w - new_w) // 2
        pil_img = pil_img.crop((left, 0, left + new_w, img_h))
    else:
        # Imagen más alta: recortar arriba/abajo
        new_h = int(img_w / target_ratio)
        top = (img_h - new_h) // 2
        pil_img = pil_img.crop((0, top, img_w, top + new_h))

    # Redimensionar base a 115% de la resolución objetivo para permitir paneos y zoom sin pérdida
    base_w = int(target_w * 1.15)
    base_h = int(target_h * 1.15)
    base_img = pil_img.resize((base_w, base_h), Image.Resampling.LANCZOS)

    # Parámetros de animación según el tipo de movimiento
    # 0: Zoom In centrado
    # 1: Zoom Out centrado
    # 2: Pan Izquierda a Derecha
    # 3: Pan Derecha a Izquierda
    # 4: Pan Abajo hacia Arriba

    def make_frame(t):
        progress = min(max(t / duration, 0.0), 1.0)
        # Suavizado de curva (ease-in-out sinusoidal)
        smooth_p = 0.5 * (1.0 - np.cos(np.pi * progress))

        if motion_type == 0:
            # Zoom In: del 100% al 110% de escala
            scale = 1.0 + 0.08 * smooth_p
            curr_w = int(target_w / scale)
            curr_h = int(target_h / scale)
            x0 = (base_w - curr_w) // 2
            y0 = (base_h - curr_h) // 2
        elif motion_type == 1:
            # Zoom Out: del 110% al 100% de escala
            scale = 1.08 - 0.08 * smooth_p
            curr_w = int(target_w / scale)
            curr_h = int(target_h / scale)
            x0 = (base_w - curr_w) // 2
            y0 = (base_h - curr_h) // 2
        elif motion_type == 2:
            # Pan Izquierda -> Derecha
            curr_w = target_w
            curr_h = target_h
            max_x = base_w - curr_w
            x0 = int(max_x * smooth_p)
            y0 = (base_h - curr_h) // 2
        elif motion_type == 3:
            # Pan Derecha -> Izquierda
            curr_w = target_w
            curr_h = target_h
            max_x = base_w - curr_w
            x0 = int(max_x * (1.0 - smooth_p))
            y0 = (base_h - curr_h) // 2
        else:
            # Pan Abajo -> Arriba
            curr_w = target_w
            curr_h = target_h
            max_y = base_h - curr_h
            x0 = (base_w - curr_w) // 2
            y0 = int(max_y * (1.0 - smooth_p))

        cropped = base_img.crop((x0, y0, x0 + curr_w, y0 + curr_h))
        if cropped.size != (target_w, target_h):
            cropped = cropped.resize((target_w, target_h), Image.Resampling.BILINEAR)

        return np.array(cropped)

    return VideoClip(make_frame, duration=duration)


def assemble_final_video(
    images_dir: Path = IMAGENES_DIR,
    audio_path: Path = AUDIO_PATH,
    output_path: Path = DEFAULT_OUTPUT_VIDEO,
    timeline_file: Path = TIMELINE_FILE,
    target_fps: int = 24,
    resolution: tuple[int, int] = (1920, 1080)
) -> bool:
    """
    Ensambla las imágenes conceptuales con movimiento Ken Burns y el audio maestro de 17:08 min.
    """
    print("=" * 65)
    print("🎬 INICIANDO ENSAMBLADOR DE VIDEO CONCEPTUAL (Efecto Ken Burns)")
    print(f"📁 Directorio de imágenes: {images_dir}")
    print(f"🎵 Pista de audio: {audio_path}")
    print(f"💾 Video final: {output_path}")
    print("=" * 65)

    if not audio_path.exists():
        print(f"❌ Error: No se encontró la pista de audio en '{audio_path}'.")
        return False

    try:
        from moviepy.editor import AudioFileClip, concatenate_videoclips
    except ImportError:
        print("❌ Error: 'moviepy' no está instalado. Ejecuta: pip install moviepy")
        return False

    # Cargar audio
    print("⏳ Analizando pista de audio maestro...")
    audio_clip = AudioFileClip(str(audio_path))
    duracion_audio = audio_clip.duration
    print(f"⏱️ Duración exacta de audio: {duracion_audio / 60:.2f} minutos ({duracion_audio:.1f}s)")

    # Cargar timeline
    timeline = []
    if timeline_file.exists():
        try:
            with open(timeline_file, "r", encoding="utf-8") as f:
                timeline = json.load(f)
        except Exception:
            pass

    # Si no hay timeline, detectar imágenes en carpeta
    image_files = sorted(list(images_dir.glob("escena_*.png")))
    if not image_files:
        print(f"❌ Error: No se encontraron imágenes en '{images_dir}'.")
        print("Ejecuta primero la generación de imágenes con 'python generate_images.py'.")
        return False

    print(f"🖼️ Imágenes encontradas: {len(image_files)}")

    # Construir clips animados
    clips_animados = []
    duracion_acumulada = 0.0

    # Distribuir duraciones
    for idx, img_p in enumerate(image_files):
        # Obtener duración del timeline si existe
        if idx < len(timeline) and "duration" in timeline[idx]:
            dur_escena = float(timeline[idx]["duration"])
        else:
            # Duración aleatoria entre 13 y 18s
            dur_escena = random.uniform(13.0, 18.0)

        # Seleccionar patrón de movimiento variado
        motion = idx % 5

        print(f"  • Procesando escena {idx + 1}/{len(image_files)}: {img_p.name} ({dur_escena:.1f}s, Movimiento #{motion})")
        clip = create_ken_burns_clip(
            img_p,
            duration=dur_escena,
            target_resolution=resolution,
            fps=target_fps,
            motion_type=motion
        )
        clips_animados.append(clip)
        duracion_acumulada += dur_escena

    print(f"\n⏱️ Duración total de imágenes calculada: {duracion_acumulada:.1f}s (Audio: {duracion_audio:.1f}s)")

    # Si la duración de las imágenes es menor que el audio, estiramos o repetimos el ciclo
    if duracion_acumulada < duracion_audio:
        factor_ajuste = duracion_audio / duracion_acumulada
        print(f"ℹ️ Ajustando ligeramente la velocidad de visualización ({factor_ajuste:.2f}x) para sincronización perfecta al 100% con el audio...")
        # Re-crear con duración escalada
        clips_animados = []
        for idx, img_p in enumerate(image_files):
            if idx < len(timeline) and "duration" in timeline[idx]:
                dur_base = float(timeline[idx]["duration"])
            else:
                dur_base = 15.0
            dur_escena = dur_base * factor_ajuste
            motion = idx % 5
            clip = create_ken_burns_clip(img_p, duration=dur_escena, target_resolution=resolution, fps=target_fps, motion_type=motion)
            clips_animados.append(clip)

    print("🔗 Concatenando escenas animadas...")
    video_concatenado = concatenate_videoclips(clips_animados, method="compose")

    # Cortar exactamente a la longitud del audio
    video_final = video_concatenado.subclip(0, duracion_audio)
    video_final = video_final.set_audio(audio_clip)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_suffix(".mp4.tmp")

    print(f"🚀 Renderizando video final a {resolution[0]}x{resolution[1]} @ {target_fps} fps (H.264 / AAC)...")
    video_final.write_videofile(
        str(temp_output),
        fps=target_fps,
        codec="libx264",
        audio_codec="aac",
        bitrate="6000k",
        audio_bitrate="192k",
        threads=4,
        preset="medium"
    )

    if temp_output.exists():
        if output_path.exists():
            output_path.unlink()
        temp_output.rename(output_path)

    audio_clip.close()
    video_final.close()

    print("\n" + "=" * 65)
    print("🎉 ¡VIDEO FINAL DE YOUTUBE GENERADO EXITOSAMENTE!")
    print(f"📁 Archivo final: {output_path.resolve()}")
    print(f"📊 Peso: {output_path.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"⏱️ Duración: {duracion_audio / 60:.2f} minutos")
    print("=" * 65)
    return True


def main():
    parser = argparse.ArgumentParser(description="Ensamblador de video con efecto Ken Burns para YouTube")
    parser.add_argument("--images-dir", type=Path, default=IMAGENES_DIR, help="Directorio con las imágenes PNG")
    parser.add_argument("--audio", type=Path, default=AUDIO_PATH, help="Ruta al archivo de audio maestro")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_VIDEO, help="Ruta del video resultante")
    parser.add_argument("--fps", type=int, default=24, help="Cuadros por segundo (default: 24)")
    args = parser.parse_args()

    success = assemble_final_video(
        images_dir=args.images_dir,
        audio_path=args.audio,
        output_path=args.output,
        target_fps=args.fps
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
