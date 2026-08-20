"""Tareas secuenciales CrewAI para producir el video de habitos evergreen."""

from crewai import Task

from config.agents import (
	guionista_bmad,
	investigador_bmad,
	prompt_engineer_bmad,
)


tarea_investigacion = Task(
	description=(
		"Investiga y estructura el contenido para un video de YouTube de 10 a 15 "
		"minutos titulado '10 Habitos de Vida Evergreen'. Aplica la metodologia "
		"BMAD para analizar el nicho de desarrollo personal y seleccionar exactamente "
		"10 habitos que mantengan su valor con el paso del tiempo, sean realistas "
		"para una audiencia general y puedan explicarse con ejemplos concretos.\n\n"
		"Para cada habito, entrega: nombre memorable, problema que resuelve, "
		"beneficio principal, evidencia o razonamiento prudente que lo respalda, "
		"primer paso accionable, objecion habitual y una idea visual o ejemplo de "
		"la vida cotidiana. Ordena los diez puntos para crear una progresion de "
		"retencion: comienza con un gancho fuerte, alterna ideas de impacto rapido "
		"con ideas profundas, abre bucles de curiosidad y reserva una revelacion o "
		"sintesis poderosa para el cierre. Incluye tambien el perfil de audiencia, "
		"la promesa central, el gancho inicial, transiciones sugeridas y los riesgos "
		"de exageracion, pseudociencia o consejos medicos que deben evitarse."
	),
	expected_output=(
		"Un informe de investigacion en Markdown, claro y util para el siguiente "
		"agente. Debe contener: (1) audiencia objetivo y promesa del video; "
		"(2) estrategia de retencion con gancho, bucles de curiosidad, ritmo y "
		"cierre; (3) una tabla o seccion numerada con exactamente 10 habitos, cada "
		"uno con su razon de inclusion, beneficio, ejemplo, objecion y accion "
		"inicial; (4) el orden narrativo recomendado y las transiciones entre "
		"puntos; y (5) notas de rigor para no presentar afirmaciones sin respaldo "
		"como hechos. No escribas aun el guion completo."
	),
	agent=investigador_bmad,
)


tarea_guion = Task(
	description=(
		"Usa exclusivamente el informe de investigacion recibido como contexto y "
		"escribe el guion narrativo final para '10 Habitos de Vida Evergreen'. "
		"Redactalo palabra por palabra en espanol, con una extension aproximada "
		"de 1800 palabras, adecuada para un video de 10 a 15 minutos. Mantiene "
		"exactamente los diez habitos aprobados en la investigacion y respeta su "
		"orden estrategico.\n\n"
		"Construye una apertura que capture la atencion en los primeros segundos, "
		"una promesa clara, desarrollo con ritmo variable, ejemplos cotidianos, "
		"micro-ganchos y transiciones naturales. Para cada habito incluye una "
		"explicacion comprensible, una aplicacion practica y una frase de conexion "
		"con el siguiente. Termina con una sintesis memorable y una llamada a la "
		"accion concreta, sin sonar artificial. Separa claramente la narracion de "
		"las indicaciones visuales para que el proximo agente pueda extraerlas. "
		"No inventes datos, citas ni promesas de salud; usa lenguaje responsable "
		"cuando el informe marque limites o incertidumbre."
	),
	expected_output=(
		"Un archivo Markdown con un guion completo de aproximadamente 1800 palabras, "
		"listo para grabar. Debe incluir titulo de trabajo, gancho inicial, "
		"introduccion, diez secciones numeradas en el orden investigado y cierre "
		"con llamada a la accion. Cada seccion debe contener texto de voz en off "
		"palabra por palabra y una descripcion visual separada, especifica y "
		"coherente. Incluye transiciones entre secciones y comprueba que el guion "
		"mantenga una sola promesa editorial, un ritmo apto para 10-15 minutos y "
		"un tono humano, practico y responsable."
	),
	agent=guionista_bmad,
	context=[tarea_investigacion],
	output_file="outputs/guion_final.md",
)


tarea_prompts = Task(
	description=(
		"Usa exclusivamente el guion final recibido como contexto. Extrae sus "
		"descripciones visuales y conviertelas en prompts cinematograficos en "
		"ingles, optimizados para Google Veo. Conserva el significado de cada "
		"escena y crea una secuencia visual consistente para un video de 10 a 15 "
		"minutos sobre '10 Habitos de Vida Evergreen'.\n\n"
		"Cada prompt debe describir una sola accion principal e incluir sujeto, "
		"accion, entorno, hora del dia, composicion, movimiento de camara, lente, "
		"profundidad de campo, iluminacion, paleta, atmosfera, estilo realista, "
		"duracion sugerida y relacion 16:9. Define al principio una biblia visual "
		"breve para mantener consistentes personajes, vestuario, espacios y "
		"objetos recurrentes. Evita texto en pantalla, logotipos, marcas, manos "
		"deformadas, cambios de identidad, saltos temporales no indicados y "
		"elementos que contradigan la narracion. No traduzcas literalmente si una "
		"formulacion audiovisual mas precisa comunica mejor la intencion."
	),
	expected_output=(
		"Un archivo Markdown en ingles listo para alimentar un flujo de generacion "
		"de video. Debe contener: (1) una seccion de continuidad visual con la "
		"descripcion de los elementos recurrentes; (2) prompts numerados y "
		"ordenados segun el guion; (3) para cada prompt, una referencia breve a "
		"la seccion narrativa, la accion principal, la voz o intencion emocional "
		"que acompana y el prompt completo en ingles; y (4) notas globales de "
		"continuidad, formato 16:9 y restricciones visuales. Los prompts deben "
		"ser ultra-detallados, no redundantes y directamente utilizables por "
		"Google Veo."
	),
	agent=prompt_engineer_bmad,
	context=[tarea_guion],
	output_file="outputs/prompts_video.md",
)


__all__ = [
	"tarea_investigacion",
	"tarea_guion",
	"tarea_prompts",
]
