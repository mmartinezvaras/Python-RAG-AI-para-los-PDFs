"""The "Cómo está hecho" page: what the project uses, the steps, the problems found on the way
and the technologies. Written for someone who comes from the CV, not for an engineer.

Same look as the credit-scoring demo (eyebrow, big sans-serif title, stat tiles, numbered
sections, step grid, chips), built on this demo's theme variables so Claro / Noche work here too.
Static text: pure functions, unit-tested.
"""

REPO = "https://github.com/mmartinezvaras/Python-RAG-AI-para-los-PDFs"

STATS = [
    ("87 %", "de las preguntas encuentran el artículo correcto"),
    ("100 %", "de las preguntas ajenas a la ley se rechazan"),
    ("501", "fragmentos del BOE en la base de datos"),
]

# (title, what happens) — the path of a question, in order
STEPS = [
    ("Leer el PDF", "Descarga el texto oficial del BOE y quita cabeceras y pies de página."),
    ("Trocear", "Lo parte en fragmentos de 1.000 caracteres y anota en cada uno su artículo y su página."),
    ("Indexar", "Convierte cada fragmento en un vector (embedding) y lo guarda en ChromaDB."),
    ("Buscar", "Busca a la vez por significado y por palabras exactas, y junta las dos listas."),
    ("Filtrar", "Si ningún fragmento se parece lo bastante, dice que no está en la ley sin preguntar a la IA."),
    ("Responder", "La IA responde solo con esos 5 fragmentos y cita cada dato con su número."),
]

# (problem, how it was solved)
PROBLEMS = [
    (
        "La búsqueda por significado fallaba con cifras y números de artículo.",
        "Añadí una búsqueda por palabras clave (BM25, escrita desde cero) y fusioné las dos listas con "
        "Reciprocal Rank Fusion. El artículo correcto aparece en el 87 % de las preguntas, frente al 80 %.",
    ),
    (
        "Una IA tiende a inventar cuando no sabe la respuesta.",
        "Antes de llamar al modelo se mira la similitud del mejor fragmento. Si no llega al umbral, la "
        "respuesta es «no está en el documento». El umbral se calibra con la evaluación.",
    ),
    (
        "Las preguntas en inglés encontraban artículos equivocados.",
        "La pregunta se traduce al español solo para buscar. Después el modelo empezó a responder en "
        "español, así que el prompt termina indicando el idioma de la respuesta.",
    ),
    (
        "No sabía si un cambio mejoraba o empeoraba el sistema.",
        "Creé 35 preguntas con respuesta conocida (5 de ellas fuera de la ley). Se evalúan en cada cambio "
        "y comparan la búsqueda híbrida con la solo vectorial.",
    ),
    (
        "Publicar la demo en Hugging Face Spaces exigía un plan de pago.",
        "La demo online está en Streamlit Community Cloud con Gemini (gratis). En local funciona con "
        "Ollama, sin claves y sin que los documentos salgan del ordenador.",
    ),
    (
        "La cuota gratuita de Gemini (1.000 embeddings al día) se gastaba en cada reinicio de la demo.",
        "Los embeddings del documento se calculan una vez en GitHub Actions y se guardan en el repositorio. "
        "La demo arranca sin gastar cuota; solo las preguntas de los visitantes la usan.",
    ),
    (
        "El servidor del BOE a veces no respondía y la demo no arrancaba.",
        "Reintentos al descargar y una copia del PDF oficial dentro del repositorio.",
    ),
    (
        "Instalar Ollama en GitHub Codespaces fallaba por una fuente de paquetes rota.",
        "Un script de instalación que lo sortea, y un test en CI que arranca el contenedor real y le "
        "hace una pregunta.",
    ),
]

# (technology, what it is used for)
TECH = [
    ("Python", "Todo el proyecto"),
    ("LangChain", "Leer los PDF y trocearlos"),
    ("ChromaDB", "Base de datos de vectores"),
    ("Ollama", "Modelos en local: Llama 3.2 3B y nomic-embed-text"),
    ("Gemini", "Modelos en la demo online, con su API compatible con OpenAI"),
    ("BM25 + RRF", "Búsqueda por palabras clave y fusión de resultados"),
    ("Streamlit", "La web, con respuesta en streaming"),
    ("pytest + ruff", "Tests automáticos y revisión del estilo del código"),
    ("GitHub Actions", "Tests, evaluación y capturas en cada cambio"),
    ("Docker · Codespaces", "Ejecutarlo en cualquier sitio con un clic"),
]

RESULTS = [
    ("Encuentra el artículo correcto (hit@5)", "87 %", "80 %"),
    ("Respuestas correctas", "77 %", "70 %"),
    ("Preguntas fuera de la ley rechazadas", "100 %", "100 %"),
]

NEXT = [
    "Un reranker que reordene los 5 fragmentos antes de responder.",
    "Un modelo más grande: el de 3B a veces confunde dos artículos parecidos.",
    "Mejorar las preguntas que no usan las palabras de la ley («¿a qué edad se puede trabajar?»).",
]

PROJECT_CSS = """
<style>
.hx { font-family: "Public Sans", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif; color: var(--lx-ink); }
.hx-eyebrow { font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--lx-ink-2); font-weight: 600; }
.hx-hero h1 { font-family: inherit; font-size: clamp(2rem, 5vw, 2.6rem); line-height: 1.08; letter-spacing: -.025em;
  font-weight: 700; margin: .4rem 0 .8rem; padding: 0; color: var(--lx-ink); }
.hx-lead { font-size: 1.12rem; line-height: 1.55; color: var(--lx-ink-2); margin: 0 0 1.4rem; max-width: 40em; }
.hx-lead b { color: var(--lx-ink); font-weight: 600; }
.hx-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: .75rem; margin-bottom: .6rem; }
.hx-stat { background: var(--lx-sheet); border-radius: 14px; padding: .9rem 1rem; box-shadow: 0 0 0 1px var(--lx-ring), var(--lx-lift); }
.hx-stat b { display: block; font-size: 1.45rem; letter-spacing: -.02em; color: var(--lx-ink); font-variant-numeric: tabular-nums; }
.hx-stat span { font-size: .85rem; color: var(--lx-ink-2); line-height: 1.35; display: block; }

.hx-section { display: flex; align-items: baseline; gap: .6rem; margin: 2.4rem 0 .2rem; }
.hx-section .n { font-size: .8rem; font-weight: 600; color: var(--lx-ink-2); font-variant-numeric: tabular-nums; }
.hx-section h3 { font-family: inherit; font-size: 1.3rem; letter-spacing: -.015em; margin: 0; padding: 0; font-weight: 650; color: var(--lx-ink); }
.hx-hint { color: var(--lx-ink-2); font-size: .95rem; line-height: 1.55; margin: .3rem 0 .9rem; max-width: 42em; }
.hx-hint b { color: var(--lx-ink); font-weight: 600; }

.hx-card { background: var(--lx-sheet); border-radius: 16px; padding: 1.3rem 1.5rem; box-shadow: 0 0 0 1px var(--lx-ring), var(--lx-lift); }
.hx-pipe { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; }
.hx-pipe div { background: var(--lx-sheet); border-radius: 12px; padding: .8rem .85rem; font-size: .86rem; color: var(--lx-ink-2);
  line-height: 1.4; box-shadow: 0 0 0 1px var(--lx-ring); }
.hx-pipe b { display: block; color: var(--lx-ink); font-size: .92rem; margin-bottom: .2rem; }
.hx-pipe b i { font-style: normal; color: var(--lx-ink-2); font-variant-numeric: tabular-nums; margin-right: .25rem; }

.hx-row { display: grid; grid-template-columns: 1fr 1.25fr; gap: 1.2rem; padding: .9rem 0; border-top: 1px solid var(--lx-rule); }
.hx-row:first-child { border-top: none; padding-top: 0; }
.hx-row:last-child { padding-bottom: 0; }
.hx-row small { display: block; font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; font-weight: 600;
  color: var(--lx-ink-2); margin-bottom: .2rem; }
.hx-row p { margin: 0; font-size: .94rem; line-height: 1.5; color: var(--lx-ink); }
.hx-row .sol p { color: var(--lx-ink-2); }

table.hx-t { width: 100%; border-collapse: collapse; font-size: .9rem; font-variant-numeric: tabular-nums; }
table.hx-t th { text-align: left; font-weight: 600; color: var(--lx-ink-2); font-size: .78rem; padding: .45rem .5rem; border-bottom: 1px solid var(--lx-rule); }
table.hx-t td { padding: .55rem .5rem; border-bottom: 1px solid var(--lx-rule); color: var(--lx-ink); }
table.hx-t tr:last-child td { border-bottom: none; }
table.hx-t td:not(:first-child), table.hx-t th:not(:first-child) { text-align: right; white-space: nowrap; }
table.hx-t td.win { font-weight: 700; }

.hx-chips { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0 0 1rem; }
.hx-chips span { font-size: .8rem; padding: .28rem .7rem; border-radius: 999px; background: var(--lx-sheet); color: var(--lx-ink);
  box-shadow: inset 0 0 0 1px var(--lx-rule); }
.hx-tech { display: grid; grid-template-columns: 11rem 1fr; gap: 0 1rem; margin: 0; }
.hx-tech dt, .hx-tech dd { margin: 0; padding: .55rem 0; border-top: 1px solid var(--lx-rule); font-size: .92rem; line-height: 1.4; }
.hx-tech dt { font-weight: 600; color: var(--lx-ink); }
.hx-tech dd { color: var(--lx-ink-2); }
.hx-tech dt:first-of-type, .hx-tech dd:first-of-type { border-top: none; padding-top: 0; }
.hx-list { margin: 0; padding-left: 1.1rem; }
.hx-list li { font-size: .94rem; line-height: 1.5; color: var(--lx-ink); margin: .25rem 0; }
.hx-foot { margin-top: 2.8rem; font-size: .85rem; color: var(--lx-ink-2); text-align: center; line-height: 1.6; }
.hx a { color: var(--lx-ink) !important; text-underline-offset: 3px; }

/* Gentle entrance of the header, only when the page opens */
@media (prefers-reduced-motion: no-preference) {
  .hx-hero > * { opacity: 0; transform: translateY(6px); animation: hx-in 420ms var(--lx-ease-out) forwards; }
  .hx-hero > *:nth-child(2) { animation-delay: 50ms; }
  .hx-hero > *:nth-child(3) { animation-delay: 100ms; }
  .hx-hero > *:nth-child(4) { animation-delay: 150ms; }
}
@keyframes hx-in { to { opacity: 1; transform: none; } }

@media (max-width: 640px) {
  .hx-stats { grid-template-columns: 1fr; }
  .hx-pipe { grid-template-columns: 1fr 1fr; }
  .hx-row { grid-template-columns: 1fr; gap: .5rem; }
  .hx-tech { grid-template-columns: 1fr; }
  .hx-tech dd { border-top: none; padding-top: 0; }
}
</style>
"""


def _section(n: int, title: str, hint: str = "") -> str:
    return (
        f'<div class="hx-section"><span class="n">{n:02d}</span><h3>{title}</h3></div>'
        + (f'<p class="hx-hint">{hint}</p>' if hint else "")
    )


def project_html() -> str:
    stats = "".join(f'<div class="hx-stat"><b>{v}</b><span>{t}</span></div>' for v, t in STATS)
    steps = "".join(f"<div><b><i>{i}</i>{t}</b>{d}</div>" for i, (t, d) in enumerate(STEPS, 1))
    problems = "".join(
        f'<div class="hx-row"><div><small>Problema</small><p>{p}</p></div>'
        f'<div class="sol"><small>Solución</small><p>{s}</p></div></div>'
        for p, s in PROBLEMS
    )
    results = "".join(
        f'<tr><td>{m}</td><td class="win">{h}</td><td>{v}</td></tr>' for m, h, v in RESULTS
    )
    chips = "".join(f"<span>{t}</span>" for t, _ in TECH)
    tech = "".join(f"<dt>{t}</dt><dd>{d}</dd>" for t, d in TECH)
    upcoming = "".join(f"<li>{x}</li>" for x in NEXT)
    return f"""
<div class="hx">
  <div class="hx-hero">
    <div class="hx-eyebrow">Proyecto de portfolio · IA generativa (RAG)</div>
    <h1>Cómo está hecho el asistente del Estatuto</h1>
    <p class="hx-lead">Un asistente que responde preguntas sobre una ley de más de 100 páginas
    <b>citando el artículo y la página</b> de cada dato, y que dice <b>«no está en la ley»</b> en vez de inventar.
    Aquí explico los pasos, los problemas que encontré y las tecnologías que he usado.</p>
    <div class="hx-stats">{stats}</div>
  </div>

  {_section(1, "La idea, en una frase",
     "Es como un examen <b>a libro abierto</b>: antes de responder, el sistema busca en el Estatuto los "
     "fragmentos que hablan de tu pregunta y se los da a la IA, que solo puede usar eso. La técnica se llama "
     "<b>RAG</b> (Retrieval-Augmented Generation: generación aumentada con búsqueda).")}

  {_section(2, "Los pasos", "Lo que pasa desde que se lee el PDF hasta que aparece la respuesta.")}
  <div class="hx-pipe">{steps}</div>

  {_section(3, "Los resultados",
     "Medido con 35 preguntas de respuesta conocida, con el modelo local (Llama 3.2 3B) en GitHub Actions. "
     "Con 30 preguntas que sí están en la ley, cada una vale unos 3 puntos.")}
  <div class="hx-card">
    <table class="hx-t">
      <tr><th>Qué se mide</th><th>Búsqueda híbrida</th><th>Solo por significado</th></tr>
      {results}
    </table>
  </div>

  {_section(4, "Los problemas y cómo los resolví",
     "Lo que no funcionaba a la primera. Casi todo lo detectaron los tests y la evaluación.")}
  <div class="hx-card">{problems}</div>

  {_section(5, "Las tecnologías")}
  <div class="hx-chips">{chips}</div>
  <div class="hx-card"><dl class="hx-tech">{tech}</dl></div>

  {_section(6, "Lo siguiente que probaría", "La evaluación está ahí para medir si cada idea mejora de verdad.")}
  <div class="hx-card"><ul class="hx-list">{upcoming}</ul></div>

  <div class="hx-foot">Datos: texto consolidado del Estatuto de los Trabajadores (BOE).
  Demo educativa, no sustituye el consejo de un abogado.<br>
  <a href="{REPO}" target="_blank">Ver el código en GitHub →</a> ·
  <a href="{REPO}/blob/main/eval/results.md" target="_blank">Ver la evaluación completa →</a></div>
</div>
"""
