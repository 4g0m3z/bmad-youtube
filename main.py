"""Punto de entrada del pipeline BMAD para generar el video de YouTube."""

import os
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

# Forzar a LiteLLM y al SDK a reintentar de forma autónoma en baches de cuota:
os.environ["LITELLM_RETRY_STRATEGY"] = "exponential_backoff"
os.environ["LITELLM_MAX_RETRIES"] = "7"

# El resto de tus imports actuales siguen aquí abajo...
from dotenv import load_dotenv
from crewai import Crew, Process
# ... (deja el resto del archivo exactamente igual)


os.makedirs("outputs", exist_ok=True)
 

from config.agents import (
	guionista_bmad,
	investigador_bmad,
	prompt_engineer_bmad,
)
from config.tasks import tarea_guion, tarea_investigacion, tarea_prompts


load_dotenv()


def iniciar_pipeline():
	"""Ejecuta la tripulacion BMAD y devuelve el resultado de CrewAI."""
	try:
		if not os.getenv("GEMINI_API_KEY"):
			raise RuntimeError(
				"Falta la variable de entorno GEMINI_API_KEY. "
				"Definela en el archivo .env antes de ejecutar el pipeline."
			)

		crew = Crew(
			agents=[
				investigador_bmad,
				guionista_bmad,
				prompt_engineer_bmad,
			],
			tasks=[tarea_investigacion, tarea_guion, tarea_prompts],
			process=Process.sequential,
			verbose=True,
		)

		return crew.kickoff()

	except Exception as error:
		print(f"Error al ejecutar el pipeline BMAD: {error}")
		return None


if __name__ == "__main__":
	resultado = iniciar_pipeline()
	if resultado is not None:
		print("Pipeline BMAD completado correctamente.")
