"""Web demo: ask questions about the Workers' Statute, watch the answer stream in, check every citation.

Run with:  streamlit run app.py
"""

import json
import os
import re
import urllib.request
from pathlib import Path

import streamlit as st

# On Streamlit Community Cloud the settings come from the app's "Secrets".
# Copy them into the environment before rag.config reads it.
try:
    for _key, _value in st.secrets.items():
        if isinstance(_value, str | int | float):
            os.environ.setdefault(_key, str(_value))
except Exception:  # no secrets file: running locally
    pass

from rag import config  # noqa: E402
from rag.answer import stream_answer  # noqa: E402
from rag.documents import page_link, source_info  # noqa: E402
from rag.ingest import build_database, get_collection  # noqa: E402
from ui import components as ui  # noqa: E402
from ui.theme import page_css  # noqa: E402

# (button label, icon, question)
EXAMPLES = [
    ("Días de vacaciones", "beach_access", "¿Cuántos días de vacaciones al año me corresponden?"),
    ("Periodo de prueba", "hourglass_top", "¿Cuánto dura como máximo el periodo de prueba de un técnico titulado?"),
    ("Despido improcedente", "gavel", "¿Qué indemnización corresponde por un despido improcedente?"),
    ("Horas extra al año", "more_time", "¿Cuántas horas extra se pueden hacer como máximo al año?"),
    ("Pregunta en inglés", "translate", "How many days of paid annual leave does a worker get?"),
    ("Algo que no está en la ley", "help", "¿Quién ganó el Tour de Francia en 2018?"),
]
THEMES = {"auto": ("brightness_auto", "Auto"), "light": ("light_mode", "Claro"), "dark": ("dark_mode", "Noche")}
MAX_UPLOAD_MB = 25

st.set_page_config(page_title="Pregunta al Estatuto de los Trabajadores", page_icon=":material/balance:")
# The theme switch can be cleared (None): fall back to following the system setting.
st.markdown(page_css(st.session_state.get("theme") or "auto"), unsafe_allow_html=True)


# ---------- Helpers ----------
def ollama_models() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=3) as resp:
            return [m["name"] for m in json.load(resp).get("models", [])]
    except Exception:
        return None


def has_model(installed: list[str], name: str) -> bool:
    return any(m == name or m == f"{name}:latest" for m in installed)


def pdf_files() -> list[Path]:
    return sorted(p for p in config.DATA_PATH.rglob("*.pdf"))


@st.cache_resource(show_spinner="Preparando el documento (solo la primera vez, puede tardar unos minutos)…")
def ensure_index() -> int:
    collection = get_collection()
    if collection.count() == 0:
        build_database()
    return collection.count()


def set_question(q: str):
    st.session_state.question = q


def html(fragment: str, target=st):
    target.markdown(fragment, unsafe_allow_html=True)


def render_result(answer, slot, animate: bool = True):
    if not answer.grounded:
        html(ui.not_found_card(answer.text, answer.best_relevance, config.MIN_RELEVANCE), slot)
        return
    html(ui.answer_card(answer.text), slot)
    cited = [p.number for p in answer.cited]
    html(ui.sources_section(answer.passages, cited, lambda p: page_link(p.source, p.page), animate=animate))


# ---------- Header ----------
_, theme_col = st.columns([3, 2])
theme_col.segmented_control(
    "Tema",
    options=list(THEMES),
    format_func=lambda k: f":material/{THEMES[k][0]}: {THEMES[k][1]}",
    default="auto",
    key="theme",
    label_visibility="collapsed",
)
html(
    '<header class="lx-hero"><h1>¿Qué dice el Estatuto de los Trabajadores?</h1>'
    "<p>Pregunta en español o en inglés. La respuesta sale <strong>solo</strong> del texto oficial del BOE "
    "y cita el artículo y la página de donde viene; si no está en la ley, te lo dice.</p></header>"
)

# ---------- Health checks (local Ollama only) ----------
if "ollama" in (config.LLM_PROVIDER, config.EMBEDDING_PROVIDER):
    installed = ollama_models()
    if installed is None:
        st.error(
            f"No se puede conectar con Ollama en `{config.OLLAMA_URL}`. Arráncalo con `ollama serve` "
            "(en GitHub Codespaces arranca solo: espera unos segundos y recarga).",
            icon=":material/power_off:",
        )
        st.stop()
    needed = ([config.LLM_MODEL] if config.LLM_PROVIDER == "ollama" else []) + (
        [config.EMBED_MODEL] if config.EMBEDDING_PROVIDER == "ollama" else []
    )
    missing = [m for m in needed if not has_model(installed, m)]
    if missing:
        st.warning(
            "Descargando los modelos (solo la primera vez): "
            + ", ".join(f"`{m}`" for m in missing)
            + ". Si no termina, ejecuta `ollama pull <modelo>` y recarga.",
            icon=":material/downloading:",
        )
        st.stop()

chunk_count = ensure_index()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### :material/description: Documento")
    for path in pdf_files():
        info = source_info(path.name)
        st.markdown(f"[{info.title}]({info.url})" if info else f"`{path.name}`")
    st.caption(f"{chunk_count} fragmentos indexados")

    if config.PUBLIC_DEMO:
        st.caption("Subir tus propios PDFs está disponible al ejecutar el proyecto en local o en Codespaces.")
    else:
        uploaded = st.file_uploader("Añade tu propio PDF", type="pdf")
        if uploaded is not None and st.session_state.get("last_upload") != uploaded.name:
            if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"El PDF supera {MAX_UPLOAD_MB} MB.", icon=":material/error:")
            else:
                safe_name = re.sub(r"[^\w.\-]", "_", Path(uploaded.name).name)
                target = config.DATA_PATH / "uploads" / safe_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(uploaded.getbuffer())
                with st.spinner("Indexando los fragmentos nuevos…"):
                    result = build_database(download=False)
                st.session_state.last_upload = uploaded.name
                st.success(
                    f"Añadidos {result.added} fragmentos. Los que ya existían no se han vuelto a procesar.",
                    icon=":material/check_circle:",
                )
                ensure_index.clear()
                st.rerun()

    st.divider()
    with st.expander("Cómo funciona", icon=":material/account_tree:"):
        search = "híbrida (semántica + palabras clave)" if config.RETRIEVAL_MODE == "hybrid" else "semántica"
        st.markdown(
            f"1. **Busca** los {config.TOP_K} fragmentos más relevantes: búsqueda {search}.\n"
            f"2. **Filtra:** si ninguno supera una similitud de {config.MIN_RELEVANCE:.2f}, responde que no está "
            "en el documento sin llamar al modelo.\n"
            "3. **Responde** solo con esos fragmentos y cita cada dato con su número.\n\n"
            f"Modelo `{config.LLM_MODEL}`, embeddings `{config.EMBED_MODEL}`, base vectorial ChromaDB."
        )
    st.markdown(":material/code: [Código en GitHub](https://github.com/mmartinezvaras/Python-RAG-AI-para-los-PDFs)")

# ---------- Question ----------
question = st.text_input(
    "Tu pregunta",
    key="question",
    placeholder="Por ejemplo: ¿cuántos días de vacaciones me corresponden?",
    label_visibility="collapsed",
)
cols = st.columns(3)
for i, (label, icon_name, q) in enumerate(EXAMPLES):
    cols[i % 3].button(
        label, key=f"ex{i}", icon=f":material/{icon_name}:", on_click=set_question, args=(q,), use_container_width=True
    )

if question:
    slot = st.empty()
    last = st.session_state.get("last")
    if last and last.question == question:
        # Same question (e.g. the theme changed): show the stored answer, don't ask the model again.
        render_result(last, slot, animate=False)
        st.stop()

    asked = st.session_state.setdefault("asked", 0)
    if config.PUBLIC_DEMO and asked >= config.MAX_QUESTIONS_PER_SESSION:
        st.info("Has llegado al límite de preguntas de la demo pública. ¡Gracias por probarla!", icon=":material/info:")
        st.stop()
    st.session_state.asked = asked + 1

    html(ui.searching_card(chunk_count), slot)
    try:
        answer, pieces = stream_answer(question)
        text = ""
        for piece in pieces:
            text += piece
            html(ui.answer_card(text, streaming=True), slot)
    except Exception as exc:  # a friendly message instead of a stack trace
        slot.error(f"No se ha podido responder: {exc}", icon=":material/error:")
        st.stop()

    st.session_state.last = answer
    render_result(answer, slot)
