import os
import sys
import glob
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

OUTPUTS_DIR = Path("outputs")
VIDEOS_DIR = OUTPUTS_DIR / "videos_finales"
AUDIO_PATH = OUTPUTS_DIR / "audio_maestro.mp3"
DEFAULT_OUTPUT_VIDEO = OUTPUTS_DIR / "video_final_youtube.mp4"


def find_video_clips(videos_dir: Path) -> list[Path]:
    """Busca y ordena los clips de video generados."""
    if not videos_dir.exists():
        return []
    
    # Buscar patrones escena_*.mp4
    clips = list(videos_dir.glob("escena_*.mp4"))
    # Ordenar por índice numérico si es posible
    def extract_index(path: Path) -> int:
        name = path.stem.replace("escena_", "")
        try:
            return int(name)
        except ValueError:
            return 999999
            
    clips.sort(key=extract_index)
    return clips


def assemble_final_video(
    videos_dir: Path = VIDEOS_DIR,
    audio_path: Path = AUDIO_PATH,
    output_path: Path = DEFAULT_OUTPUT_VIDEO,
    target_fps: int = 24,
    resolution: tuple[int, int] = (1920, 1080)
) -> bool:
    """
    Ensambla la secuencia de clips con la pista de audio maestro.
    """
    print("=" * 60)
    print("🎬 INICIANDO ENSAMBLE FINAL DE VIDEO (BMAD Pipeline)")
    print(f"📁 Directorio de clips: {videos_dir}")
    print(f"🎵 Pista de audio: {audio_path}")
    print(f"💾 Destino: {output_path}")
    print("=" * 60)

    if not audio_path.exists():
        print(f"❌ Error: No se encontró la pista de audio en '{audio_path}'.")
        print("Ejecuta primero 'python generate_voice.py' para generar la narración.")
        return False

    clips_paths = find_video_clips(videos_dir)
    if not clips_paths:
        print(f"❌ Error: No se encontraron clips de video en '{videos_dir}'.")
        print("Ejecuta 'python generate_video_premium.py' para generar los clips de video.")
        return False

    print(f"📦 Clips de video encontrados: {len(clips_paths)}")

    try:
        from moviepy.editor import (
            VideoFileClip,
            AudioFileClip,
            concatenate_videoclips,
            CompositeVideoClip
        )
    except ImportError:
        print("❌ Error: 'moviepy' no está instalado.")
        print("Instálalo ejecutando: pip install moviepy imageio-ffmpeg")
        return False

    try:
        print("⏳ Cargando pista de audio...")
        audio_clip = AudioFileClip(str(audio_path))
        duracion_audio = audio_clip.duration
        print(f"⏱️ Duración total de audio: {duracion_audio / 60:.2f} minutos ({duracion_audio:.1f} segundos)")

        print("⏳ Cargando y estandarizando clips de video...")
        loaded_clips = []
        duracion_video_total = 0.0

        for clip_p in clips_paths:
            try:
                clip = VideoFileClip(str(clip_p))
                # Redimensionar si es necesario para mantener consistencia
                if clip.size != list(resolution):
                    clip = clip.resize(resolution)
                loaded_clips.append(clip)
                duracion_video_total += clip.duration
            except Exception as e:
                print(f"⚠️ Advertencia: No se pudo cargar el clip '{clip_p.name}': {e}")

        if not loaded_clips:
            print("❌ Error: No se pudieron cargar clips de video válidos.")
            return False

        print(f"⏱️ Duración combinada de clips cargados: {duracion_video_total:.1f} segundos")

        # Si el audio es más largo que la suma de clips, repetimos/distribuimos la secuencia en bucle
        clips_para_concatenar = list(loaded_clips)
        if duracion_video_total < duracion_audio:
            repeticiones_necesarias = int(duracion_audio // duracion_video_total) + 1
            print(
                f"ℹ️ La duración de clips ({duracion_video_total:.1f}s) es menor a la narración ({duracion_audio:.1f}s). "
                f"Componiendo ciclo de {repeticiones_necesarias} pasadas para cubrir el metraje completo..."
            )
            clips_para_concatenar = loaded_clips * repeticiones_necesarias

        print("🔗 Concatenando clips de video...")
        video_concatenado = concatenate_videoclips(clips_para_concatenar, method="compose")

        # Ajustar duración exacta del video a la duración del audio
        video_final = video_concatenado.subclip(0, duracion_audio)
        video_final = video_final.set_audio(audio_clip)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output_path.with_suffix('.mp4.tmp')

        print(f"🚀 Renderizando video final a {resolution[0]}x{resolution[1]} @ {target_fps} fps...")
        video_final.write_videofile(
            str(temp_output),
            fps=target_fps,
            codec="libx264",
            audio_codec="aac",
            bitrate="8000k",
            audio_bitrate="192k",
            threads=4,
            preset="medium"
        )

        if temp_output.exists():
            if output_path.exists():
                output_path.unlink()
            temp_output.rename(output_path)

        # Liberar recursos
        audio_clip.close()
        for c in loaded_clips:
            c.close()
        video_final.close()

        print("\n" + "=" * 60)
        print("🎉 ¡VIDEO FINAL DE YOUTUBE GENERADO CON ÉXITO!")
        print(f"📁 Ubicación: {output_path.resolve()}")
        print(f"📊 Peso: {output_path.stat().st_size / (1024 * 1024):.2f} MB")
        print(f"⏱️ Duración: {duracion_audio / 60:.2f} minutos")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"❌ Error durante el ensamblado del video: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Ensamblador final de video y audio para YouTube (BMAD)")
    parser.add_argument("--clips-dir", type=Path, default=VIDEOS_DIR, help="Carpeta con los clips mp4")
    parser.add_argument("--audio", type=Path, default=AUDIO_PATH, help="Ruta al archivo audio_maestro.mp3")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_VIDEO, help="Ruta del video resultante")
    parser.add_argument("--fps", type=int, default=24, help="Cuadros por segundo (default: 24)")
    args = parser.parse_args()

    success = assemble_final_video(
        videos_dir=args.clips_dir,
        audio_path=args.audio,
        output_path=args.output,
        target_fps=args.fps
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
