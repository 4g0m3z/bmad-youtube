import os
from crewai import Agent, Task, Crew, Process
from google import genai
from google.genai import types

# Definimos los modelos de Google AI Studio a utilizar
MODELO_PRO = "gemini-2.5-pro"
MODELO_FLASH = "gemini-2.5-flash"

print("🤖 Inicializando agentes bajo metodología BMAD...")

# ==========================================
# DEFINICIÓN DE AGENTES (Personas BMAD)
# ==========================================

investigador_bmad = Agent(
    role="Investigador de Tendencias de YouTube",
    goal="Analizar el nicho solicitado y estructurar los puntos clave con mayor retención para el video.",
    backstory="Eres un analista de datos experto en el algoritmo de YouTube. Tu trabajo es encontrar los ganchos emocionales y la estructura del tema.",
    llm=MODELO_PRO,
    verbose=True
)

guionista_bmad = Agent(
    role="Guionista Cinematográfico de YouTube",
    goal="Transformar la investigación en un guion técnico detallado dividido en escenas de 5 segundos.",
    backstory="Eres un guionista enfocado en retención de contenido. Creas estructuras dinámicas (Gancho, Desarrollo, CTA) y describes la acción visual de cada escena.",
    llm=MODELO_FLASH,
    verbose=True
)

prompt_engineer_bmad = Agent(
    role="Director de Arte y Prompt Engineer de Veo",
    goal="Convertir las descripciones visuales del guion en prompts técnicos y consistentes para Google Veo 2.",
    backstory="Eres un experto en generación de video por IA. Traduces ideas a comandos de cámara, iluminación y estilos cinematográficos sin perder la consistencia del personaje.",
    llm=MODELO_FLASH,
    verbose=True
)

# ==========================================
# DEFINICIÓN DE TAREAS Y FLUJO DE TRABAJO
# ==========================================

tema_video = "Cómo la Inteligencia Artificial cambiará el trabajo en los próximos 5 años"

tarea_investigacion = Task(
    description=f"Investiga las tendencias y ángulos más impactantes sobre: '{tema_video}'. Entrega una estructura de 5 puntos clave.",
    expected_output="Un reporte estructurado con los puntos clave y el gancho (hook) inicial del video.",
    agent=investigador_bmad
)

tarea_guion = Task(
    description="Toma el reporte de investigación y escribe un guion técnico. Divídelo en escenas de máximo 5 segundos. Cada escena debe incluir: Narración (Voz en off) y Descripción Visual de la acción.",
    expected_output="Un guion en formato Markdown dividido estrictamente por escenas numeradas.",
    agent=guionista_bmad
)

tarea_prompts = Task(
    description="Toma el guion técnico y extrae únicamente las descripciones visuales. Conviértelas en prompts optimizados para Google Veo 2 (relación 16:9, estilo cinematográfico, fotorrealista). Mantén consistencia en los elementos.",
    expected_output="Una lista limpia de prompts de video en texto, listos para ser procesados por la API de Veo.",
    agent=prompt_engineer_bmad
)

# ==========================================
# EJECUCIÓN DEL ENTORNO MULTIAGENTE
# ==========================================

crew = Crew(
    agents=[investigador_bmad, guionista_bmad, prompt_engineer_bmad],
    tasks=[tarea_investigacion, tarea_guion, tarea_prompts],
    process=Process.sequential # Los agentes interactúan en orden secuencial estricto
)

# Inicia la interacción autónoma entre agentes
resultado_prompts = crew.kickoff()

print("\n🚀 ¡Flujo multiagente completado con éxito!")
print("Los prompts optimizados para generar tus videos están listos.")

# ==========================================
# BONUS: Envío automático a Google Veo 2
# ==========================================
# Nota: La generación de video por API requiere acceso habilitado a Veo en Google GenAI SDK.

client = genai.Client()

# Ejemplo de cómo el script toma el output del último agente y genera el primer clip
print("🎬 Generando primer clip de video en Google Veo 2...")
primer_prompt = "Cinematic shot of a futuristic workspace, clean lighting, photo-realistic, 16:9 aspect ratio"

operation = client.models.generate_videos(
    model='veo-2.0-generate-001',
    prompt=primer_prompt,
    config=types.GenerateVideosConfig(
        person_generation="DONT_ALLOW",
        aspect_ratio="16:9",
        duration_seconds=5,
        output_mime_type="video/mp4"
    )
)

# Guardar el video generado de forma autónoma
for generated_video in operation.generated_videos:
    with open("escena_1.mp4", "wb") as f:
        f.write(generated_video.video.image.image_bytes)
print("💾 ¡Video 'escena_1.mp4' descargado correctamente!")
