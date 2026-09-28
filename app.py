"""
Orquestador Principal y CLI Unificada del Pipeline BMAD-YouTube.
Permite ejecutar el pipeline audiovisual completo (CrewAI -> TTS -> Imágenes Conceptuales -> Ensamble Ken Burns).
"""

import os
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


def banner():
    print("=" * 65)
    print("      🚀 BMAD YOUTUBE AUTOMATED VIDEO PRODUCTION PIPELINE")
    print("=" * 65)


def check_status():
    """Muestra el estado de variables de entorno y archivos generados."""
    banner()
    print("\n📋 ESTADO DEL ENTORNO Y CLAVES DE API:")
    gemini_key = bool(os.getenv("GEMINI_API_KEY"))
    openai_key = bool(os.getenv("OPENAI_API_KEY"))
    gemini_pro = os.getenv("GEMINI_MODEL_PRO", "gemini/gemini-2.0-flash")

    print(f"  • GEMINI_API_KEY:  {'✅ Configurada (Motor Primario)' if gemini_key else '❌ Falta en .env'}")
    print(f"  • OPENAI_API_KEY:  {'✅ Configurada (TTS & DALL-E Fallback)' if openai_key else '❌ Falta en .env'}")
    print(f"  • Modelo Gemini:   {gemini_pro}")
    print(f"  • Estilo Visual:   Ilustración Animada 2D Vectorial (Flat Animation)")

    print("\n📁 ESTADO DE LOS ENTREGABLES (outputs/):")
    outputs_dir = Path("outputs")
    guion_path = outputs_dir / "guion_final.md"
    prompts_path = outputs_dir / "prompts_video.md"
    audio_path = outputs_dir / "audio_maestro.mp3"
    imagenes_dir = outputs_dir / "imagenes"
    timeline_file = outputs_dir / "scenes_timeline.json"
    final_video = outputs_dir / "video_final_youtube.mp4"

    print(f"  1. Guion Markdown:         {'✅ Listo (' + str(guion_path.stat().st_size // 1024) + ' KB)' if guion_path.exists() else '❌ Pendiente'}")
    print(f"  2. Prompts de Video:       {'✅ Listo (' + str(prompts_path.stat().st_size // 1024) + ' KB)' if prompts_path.exists() else '❌ Pendiente'}")
    print(f"  3. Audio Maestro MP3:      {'✅ Listo (' + str(audio_path.stat().st_size // (1024*1024)) + ' MB, 17:08 min)' if audio_path.exists() else '❌ Pendiente'}")

    total_imgs = len(list(imagenes_dir.glob("escena_*.png"))) if imagenes_dir.exists() else 0
    print(f"  4. Imágenes Conceptuales:  {'✅ ' + str(total_imgs) + ' imágenes generadas' if total_imgs > 0 else '❌ 0 imágenes generadas'}")
    print(f"  5. Video Final YouTube:    {'✅ Generado (' + str(final_video.stat().st_size // (1024*1024)) + ' MB)' if final_video.exists() else '❌ Pendiente'}")
    print("=" * 65 + "\n")


def run_stage_1():
    """Fase 1: CrewAI (Investigación, Guion, Prompts)"""
    print("\n🤖 [FASE 1] Ejecutando tripulación CrewAI (Investigador + Guionista + Prompt Engineer)...")
    from main import iniciar_pipeline
    res = iniciar_pipeline()
    if res is not None:
        print("✅ [FASE 1] Guion y prompts generados exitosamente en 'outputs/'.")
        return True
    else:
        print("❌ [FASE 1] Falló la generación con CrewAI.")
        return False


def run_stage_2():
    """Fase 2: OpenAI TTS (Audio maestro)"""
    print("\n🎙️ [FASE 2] Generando pista de audio maestro con OpenAI TTS...")
    from generate_voice import generar_audio_maestro_estable
    try:
        generar_audio_maestro_estable()
        return True
    except Exception as e:
        print(f"❌ [FASE 2] Error al generar audio: {e}")
        return False


def run_stage_3(max_images=None, engine="auto"):
    """Fase 3: Ilustraciones Animadas 2D (FLUX + Fallback Gemini/DALL-E)"""
    print("\n🎨 [FASE 3] Generando ilustraciones animadas 2D (FLUX ➔ Gemini ➔ DALL-E Fallback)...")
    import subprocess
    cmd = [sys.executable, "generate_images.py", "--engine", engine]
    if max_images:
        cmd.extend(["--max-images", str(max_images)])
    ret = subprocess.call(cmd)
    return ret == 0


def run_stage_4():
    """Fase 4: Ensamble Final con Efecto Ken Burns"""
    print("\n🎞️ [FASE 4] Ensamblando video final con movimiento Ken Burns y audio de 17:08 min...")
    from assemble_video import assemble_final_video
    return assemble_final_video()


def interactive_menu():
    banner()
    while True:
        print("\nSelecciona la acción a realizar:")
        print("  1. Ver estado del proyecto y diagnósticos")
        print("  2. [Fase 1] Generar Guion y Prompts (CrewAI)")
        print("  3. [Fase 2] Generar Pista de Audio Maestro (OpenAI TTS)")
        print("  4. [Fase 3] Generar Ilustraciones Animadas 2D (FLUX + Fallback)")
        print("  5. [Fase 4] Ensamblar Video Final de YouTube (MoviePy con Ken Burns)")
        print("  6. 🚀 Ejecutar PIPELINE COMPLETO (Fases 1 a 4)")
        print("  0. Salir")

        opcion = input("\nIngresa tu opción (0-6): ").strip()

        if opcion == "1":
            check_status()
        elif opcion == "2":
            run_stage_1()
        elif opcion == "3":
            run_stage_2()
        elif opcion == "4":
            max_s = input("¿Límite de imágenes a generar? (Enter para todas): ").strip()
            max_images = int(max_s) if max_s.isdigit() else None
            run_stage_3(max_images)
        elif opcion == "5":
            run_stage_4()
        elif opcion == "6":
            print("\n🚀 Iniciando Pipeline Completo...")
            if run_stage_1() and run_stage_2() and run_stage_3() and run_stage_4():
                print("\n🎉 ¡PIPELINE COMPLETO FINALIZADO CON ÉXITO!")
            else:
                print("\n⚠️ El pipeline se detuvo por un error en una de las fases.")
        elif opcion == "0":
            print("👋 Saliendo del asistente BMAD YouTube.")
            break
        else:
            print("⚠️ Opción inválida. Intenta nuevamente.")


def main():
    parser = argparse.ArgumentParser(description="Orquestador BMAD YouTube")
    parser.add_argument("--status", action="store_true", help="Muestra el estado de la configuración y entregables")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3, 4], help="Ejecuta una fase específica (1: Guion, 2: Audio, 3: Imágenes, 4: Ensamble)")
    parser.add_argument("--all", action="store_true", help="Ejecuta todo el pipeline de principio a fin")
    parser.add_argument("--max-images", type=int, default=None, help="Límite de imágenes para la fase 3")
    parser.add_argument("--engine", choices=["auto", "flux", "gemini", "dalle"], default="auto", help="Motor de imagen preferido")
    args = parser.parse_args()

    if args.status:
        check_status()
        return 0

    if args.stage == 1:
        return 0 if run_stage_1() else 1
    elif args.stage == 2:
        return 0 if run_stage_2() else 1
    elif args.stage == 3:
        return 0 if run_stage_3(args.max_images, args.engine) else 1
    elif args.stage == 4:
        return 0 if run_stage_4() else 1
    elif args.all:
        ok = run_stage_1() and run_stage_2() and run_stage_3(args.max_images, args.engine) and run_stage_4()
        return 0 if ok else 1

    interactive_menu()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
