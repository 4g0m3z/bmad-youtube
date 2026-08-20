import os
import re
import asyncio
import subprocess
import sys
import ssl
import aiohttp

# =====================================================================
# 🔥 RUNTIME MONKEY PATCH: Inyección de bajo nivel sobre el pool de aiohttp
# =====================================================================
# Forzamos un contexto SSL sin verificación para CUALQUIER conexión de aiohttp
ctx_inseguro = ssl.create_default_context()
ctx_inseguro.check_hostname = False
ctx_inseguro.verify_mode = ssl.CERT_NONE

# Guardamos la función constructora original de aiohttp
_original_init = aiohttp.ClientSession.__init__

def _patched_init(self, *args, **kwargs):
    """
    Parche que intercepta la inicialización de la sesión HTTP de edge-tts 
    y le inyecta un conector sin verificación SSL en caliente.
    """
    if "connector" not in kwargs or kwargs["connector"] is None:
        kwargs["connector"] = aiohttp.TCPConnector(ssl=ctx_inseguro)
    _original_init(self, *args, **kwargs)

# Sobrescribimos el método original en el core de la librería cargada en memoria
aiohttp.ClientSession.__init__ = _patched_init
# =====================================================================

# Autoinstalación de edge-tts si no se encuentra en el entorno .venv
try:
    import edge_tts
except ImportError:
    print("📦 Instalando la librería de audio de alto rendimiento de Microsoft (edge-tts)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts"])
    import edge_tts

GUION_PATH = "outputs/guion_final.md"
AUDIO_OUTPUT_PATH = "outputs/audio_maestro.mp3"
VOZ_CONFIGURADA = "es-MX-AlvaroNeural" 

def limpiar_guion(ruta_archivo):
    """Elimina las etiquetas y marcas técnicas de los agentes BMAD."""
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"❌ No se encontró el archivo de guion en: {ruta_archivo}")
        
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        contenido = f.read()
    
    # Remover marcas de los agentes e instrucciones
    texto_limpio = re.sub(re.compile(r'\[.*?\]'), '', contenido)
    texto_limpio = re.sub(re.compile(r'\(.*?\)' ), '', texto_limpio)
    texto_limpio = texto_limpio.replace("**Narrador:**", "").replace("**Voz en off:**", "")
    texto_limpio = re.sub(r'#+\s+.*', '', texto_limpio)
    
    lineas = [linea.strip() for linea in texto_limpio.splitlines() if linea.strip()]
    return " ".join(lineas)

async def generar_audio_async():
    print("🧹 [AUDIO_AGENT] Limpiando el archivo de texto generado por tus agentes...")
    texto_narrativo = limpiar_guion(GUION_PATH)
    
    print(f"🎤 Texto extraído con éxito ({len(texto_narrativo)} caracteres).")
    print(f"🤖 Conectando con los servidores de Microsoft TTS ({VOZ_CONFIGURADA})...")
    print("🔒 [HACK INTERNO] Parche sobre ClientSession activo. Conexión TLS interceptada.")
    
    try:
        # Inicializamos la comunicación asíncrona normal
        communicate = edge_tts.Communicate(texto_narrativo, VOZ_CONFIGURADA)
        
        print("📥 Transmitiendo y guardando el archivo consolidado de audio...")
        # Al ejecutar save(), edge_tts levantará un ClientSession que caerá en nuestra trampa de parche
        await communicate.save(AUDIO_OUTPUT_PATH)
        
        print("\n" + "="*50)
        print(f"🎉 ¡ÉXITO COMPLETADO! Tu audio de YouTube de larga duración está listo.")
        print(f"📁 Archivo de salida: '{AUDIO_OUTPUT_PATH}'")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado al consolidar el audio: {e}")

def main():
    asyncio.run(generar_audio_async())

if __name__ == "__main__":
    main()
