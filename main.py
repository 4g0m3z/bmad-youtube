import os
import sys

# Asegurar compatibilidad UTF-8 en terminales Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

# Forzar a LiteLLM y al SDK a reintentar de forma autónoma en baches de cuota:
os.environ["LITELLM_RETRY_STRATEGY"] = "exponential_backoff"
os.environ["LITELLM_MAX_RETRIES"] = "7"

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
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
