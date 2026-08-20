import os
import time
import json
import re
import sys
from google import genai
from google.genai import types
from google.genai import errors  # Importación oficial para atrapar excepciones del SDK
from dotenv import load_dotenv

# 1. Configuración de Infraestructura de AI Studio
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

OUTPUT_DIR = "outputs/videos_finales"
CHECKPOINT_FILE = "outputs/video_checkpoint.json"
PROMPTS_PATH = "outputs/prompts_video.md"

# Mantenemos el motor unificado estable que ya validó tu entorno
MODELO_CINEMATICO = 'gemini-3.1-flash-image'

os.makedirs(OUTPUT_DIR, exist_ok=True)

def cargar_progreso():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                return json.load(f).get("ultimo_id", 0)
        except json.JSONDecodeError:
            return 0
    return 0

def guardar_progreso(id_escena):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump({"ultimo_id": id_escena, "timestamp": time.ctime()}, f)

def extraer_prompts_de_md(ruta):
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"❌ No se encontró el archivo de prompts en: {ruta}")
    with open(ruta, "r", encoding="utf-8") as f:
        contenido = f.readlines()
    prompts = [l.strip() for l in contenido if l.strip() and not l.startswith(('#', '-', '['))]
    return prompts

def generar_fotograma_cinematico(id_escena, prompt_texto, client):
    frame_name = f"escena_{id_escena:03d}.jpg"
    frame_path = os.path.join(OUTPUT_DIR, frame_name)
    
    print(f"🎬 [FÁBRICA VISUAL] Generando Fotograma {id_escena}: {prompt_texto[:60]}...")
    instruccion_imagen = f"Generate a cinematic, high-fidelity 4k photorealistic image based strictly on this description: {prompt_texto}"
    
    # Política de reintentos con reloj de arena para sobrellevar el Rate Limiting (429)
    MAX_RETRIES = 5
    
    for intento in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODELO_CINEMATICO,
                contents=instruccion_imagen,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    candidate_count=1
                )
            )

            image_success = False
            if response.candidates and len(response.candidates) > 0:
                primer_candidato = response.candidates[0]
                if primer_candidato.content and primer_candidato.content.parts:
                    for part in primer_candidato.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            with open(frame_path, "wb") as f:
                                f.write(part.inline_data.data)
                            image_success = True
                            break
            
            if image_success and os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                guardar_progreso(id_escena)
                print(f"✅ FOTOGRAMA CONFIRMADO: '{frame_name}' unificado ({os.path.getsize(frame_path)/1024:.2f} KB).")
                return True
            else:
                print(f"⚠️ Estructura vacía en escena {id_escena}. Reintentando...")
                time.sleep(3)

        except Exception as e:
            error_str = str(e)
            
            # 🔥 DETECCIÓN INTERNA DE CUOTA (429 / RESOURCE_EXHAUSTED)
            if "429" in error_str or "quota" in error_str.lower() or "exhausted" in error_str.lower():
                # Calculamos un bache de espera exponencial progresivo (65s, 130s, etc.)
                segundos_espera = 65 * intento 
                
                print(f"\n🛑 [LIMITALERTA] Cuota de tokens alcanzada en escena {id_escena}.")
                print(f"⏳ La API de Google restablecerá tus tokens pronto.")
                
                # Bucle visual de cuenta regresiva solicitado en el requerimiento
                for restante in range(segundos_espera, 0, -1):
                    sys.stdout.write(f"\r🕒 Restableciendo cuota... faltan exactamente {restante} segundos para continuar pipeline.")
                    sys.stdout.flush()
                    time.sleep(1)
                
                print("\n🔄 [REANUDANDO] Reloj de arena completado. Reenviando petición al servidor...\n")
                continue # Regresa al inicio del bucle for para reintentar la MISMA escena
            else:
                print(f"❌ Excepción crítica de infraestructura en escena {id_escena}: {e}")
                return False
                
    print(f"🛑 Abortando: No se pudo liberar la cuota de la escena {id_escena} tras {MAX_RETRIES} intentos.")
    return False

def iniciar_fabrica_visual():
    if not API_KEY:
        print("❌ Error: Variable GEMINI_API_KEY vacía. Ejecuta: export GEMINI_API_KEY='tu_llave'")
        return

    client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1'})
    prompts_lista = extraer_prompts_de_md(PROMPTS_PATH)
    ultimo_id = cargar_progreso()
    
    print("\n" + "="*50)
    print(f"📊 PIPELINE VISUAL AUTOMÁTICO ACTIVO")
    print(f"📌 Total escenas en cola: {len(prompts_lista)}")
    print(f"🔄 Escena de reanudación: {ultimo_id + 1}")
    print(f"🤖 Motor cinematográfico unificado: {MODELO_CINEMATICO}")
    print("="*50)

    for idx, prompt in enumerate(prompts_lista, 1):
        if idx <= ultimo_id:
            continue
            
        exito = generar_fotograma_cinematico(idx, prompt, client)
        
        if not exito:
            print("🚪 Deteniendo pipeline de forma controlada por error de infraestructura.")
            break
            
        # Cooldown regulado de cortesía para mitigar el throttling de Google One
        time.sleep(5)

if __name__ == "__main__":
    iniciar_fabrica_visual()
