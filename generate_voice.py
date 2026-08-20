import os
import re
import time
import subprocess
import sys

# Asegurar importación de pydub en el entorno virtual
try:
    from pydub import AudioSegment
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pydub"])
    from pydub import AudioSegment

from openai import OpenAI
from dotenv import load_dotenv

# Carga de variables de entorno
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

GUION_PATH = "outputs/guion_final.md"
AUDIO_OUTPUT_PATH = "outputs/audio_maestro.mp3"

# Usaremos 'shimmer' o 'alloy'. Al acelerar ligeramente a 1.05 / 1.08 reduce el dejo anglosajón.
VOZ_CONFIGURADA = "alloy" 

def limpiar_y_parsear_guion_bmad(ruta_archivo):
    """
    Parser determinista bajo la metodología BMAD. Puga títulos (#), marcas visuales [],
    asteriscos y etiquetas de diálogo. Detecta la exención e inyecta la marca de silencio.
    """
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"❌ No se encontró el guion en: {ruta_archivo}")
        
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        lineas = f.readlines()
    
    elementos_filtrados = []
    palabras_tecnicas = [
        "escena", "scene", "narrador", "narrador:", "voz en off", "voz en off:", 
        "video", "audio", "visual", "transición", "prompt", "cta", "gancho", "introducción"
    ]
    
    for linea in lineas:
        linea_str = linea.strip()
        if not linea_str:
            continue
            
        linea_low = linea_str.lower()
        
        # ❌ REGLA 1: Omitir títulos de Markdown (#, ##, ###) y separadores (---)
        if linea_str.startswith('#') or linea_str.startswith('-'):
            continue
            
        # ❌ REGLA 2: Omitir cualquier directriz visual o técnica encerrada entre corchetes [] o paréntesis ()
        if linea_str.startswith('[') or linea_str.endswith(']') or linea_str.startswith('('):
            continue
            
        # ⚠️ REGLA 3: DETECCIÓN DE LA NOTA DE EXENCIÓN DE RESPONSABILIDAD
        if "exención de responsabilidad" in linea_low or "nota de exención" in linea_low or "puramente divulgativo" in linea_low:
            if not elementos_filtrados or elementos_filtrados[-1] != "[INJECT_SILENCE_5_SECONDS]":
                print("🎯 [SILENCE_INJECTION] Exención de responsabilidad detectada. Programando silencio...")
                elementos_filtrados.append("[INJECT_SILENCE_5_SECONDS]")
            continue

        # 🧹 REGLA 4: Limpieza interna estricta de la frase (remover asteriscos **, hashtags o símbolos >)
        linea_saneada = re.sub(r'[\*\#\_\-\`\[\]\(\)\>\<\🖳]', '', linea_str)
        
        # 🧹 REGLA 5: Purgar etiquetas de diálogo al inicio de la frase
        for palabra in palabras_tecnicas:
            linea_saneada = re.sub(r'(?i)^\s*' + re.escape(palabra) + r'\s*\:?\s*', '', linea_saneada)
            
        linea_saneada = linea_saneada.strip()
        
        if linea_saneada:
            elementos_filtrados.append(linea_saneada)
            
    return elementos_filtrados

def generar_audio_maestro_estable():
    print("🧹 [AUDIO_AGENT] Iniciando parser determinista bajo especificaciones BMAD...")
    bloques_guion = limpiar_y_parsear_guion_bmad(GUION_PATH)
    
    print(f"📦 Pipeline estructurado con éxito en {len(bloques_guion)} elementos secuenciales.")
    print(f"🤖 Conectando con la API de OpenAI TTS (Voz: {VOZ_CONFIGURADA})...")
    
    # Inicializamos un AudioSegment vacío en memoria (Fábrica digital de pydub)
    audio_unificado = AudioSegment.empty()
    temp_files = []
    
    try:
        for idx, elemento in enumerate(bloques_guion, 1):
            temp_chunk_path = f"outputs/temp_chunk_{idx}.mp3"
            
            # Inyección limpia del bache de silencio
            if elemento == "[INJECT_SILENCE_5_SECONDS]":
                print(f"🤫 [Bloque {idx}/{len(bloques_guion)}] Inyectando 5 segundos de silencio digital perfecto...")
                silencio = AudioSegment.silent(duration=5000) # 5000 milisegundos
                audio_unificado += silencio
                continue
                
            print(f"🎙️ [Bloque {idx}/{len(bloques_guion)}] Creando archivo temporal e invocando OpenAI TTS...")
            
            # Llamada tradicional a la API de OpenAI
            response = client.audio.speech.create(
                model="tts-1",
                voice=VOZ_CONFIGURADA,
                input=elemento,
                speed=1.05 # Aceleración ligera del tono para neutralizar el acento anglosajón
            )
            
            # Guardamos físicamente el fragmento para que pydub lo procese con sus decodificadores nativos
            with open(temp_chunk_path, "wb") as f:
                f.write(response.content)
            temp_files.append(temp_chunk_path)
            
            # pydub lee el archivo, analiza su bitrate y repara los encabezados de tiempo
            chunk_audio = AudioSegment.from_mp3(temp_chunk_path)
            audio_unificado += chunk_audio
            
            # Pequeño respiro técnico para evitar bloqueos por volumen de peticiones
            time.sleep(0.4)
            
        print("🔗 [CONSOLIDACIÓN MÁSTER] Compilando la pista completa y escribiendo metadatos de tiempo reales...")
        os.makedirs(os.path.dirname(AUDIO_OUTPUT_PATH), exist_ok=True)
        
        # Exportamos el archivo MP3 unificado forzando un bitrate comercial estable
        audio_unificado.export(AUDIO_OUTPUT_PATH, format="mp3", bitrate="192k")
        
        print("🧹 Eliminando fragmentos y buffers residuales de disco...")
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
        duracion_minutos = len(audio_unificado) / 1000 / 60
        print("\n" + "="*50)
        print(f"🎉 ¡FASE 3 FINALIZADA CON ÉXITO ROTUNDO!")
        print(f"⏱️  Duración exacta calculada: {duracion_minutos:.2f} minutos")
        print(f"📊 Peso real del archivo máster: {os.path.getsize(AUDIO_OUTPUT_PATH) / (1024*1024):.2f} MB")
        print(f"📁 Ubicación: '{AUDIO_OUTPUT_PATH}'")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Error crítico en la consolidación del pipeline: {e}")
        # Limpieza de emergencia por si el script se interrumpe
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

if __name__ == "__main__":
    generar_audio_maestro_estable()
