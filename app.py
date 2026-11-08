"""Web demo: ask questions about the PDFs, watch the answer stream in, check every citation.

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
from rag.answer import passage_label, stream_answer  # noqa: E402
from rag.documents import page_link, source_info  # noqa: E402
from rag.ingest import build_database, get_collection  # noqa: E402

EXAMPLES = [
    "¿Cuántos días de vacaciones al año me corresponden?",
    "¿Cuánto dura como máximo el periodo de prueba de un técnico titulado?",
    "¿Qué indemnización corresponde por un despido improcedente?",
    "¿Cuántas horas extra se pueden hacer como máximo al año?",
    "How many hours must pass between the end of one working day and the next?",
    "¿Quién ganó el Tour de Francia en 2018?",  # not in the documents → should say so
]
MAX_UPLOAD_MB = 25

st.set_page_config(page_title="Pregunta a tus PDFs", page_icon="📄", layout="centered")


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


@st.cache_resource(show_spinner="Preparando los documentos (solo la primera vez, puede tardar unos minutos)…")
def ensure_index() -> int:
    collection = get_collection()
    if collection.count() == 0:
        build_database()
    return collection.count()


def set_question(q: str):
    st.session_state.question = q


def render_citations(text: str) -> str:
    return re.sub(r"\[(\d+)\]", r" **[\1]**", text)


# ---------- Header ----------
st.title("📄 Pregunta a tus PDFs")
st.caption(
    "Demo de **RAG** (Retrieval-Augmented Generation) sobre el **Estatuto de los Trabajadores** (BOE). "
    "La respuesta se genera **solo** con los fragmentos recuperados del documento y cada dato cita "
    "su artículo y la página del PDF oficial. Si la respuesta no está en el documento, lo dice."
)

# ---------- Health checks (local Ollama only) ----------
if "ollama" in (config.LLM_PROVIDER, config.EMBEDDING_PROVIDER):
    installed = ollama_models()
    if installed is None:
        st.error(
            f"No se puede conectar con Ollama en `{config.OLLAMA_URL}`. Arráncalo con `ollama serve` "
            "(en GitHub Codespaces arranca solo: espera unos segundos y recarga)."
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
            + ". Si no termina, ejecuta `ollama pull <modelo>` y recarga."
        )
        st.stop()

chunk_count = ensure_index()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Documentos")
    for path in pdf_files():
        info = source_info(path.name)
        st.markdown(f"- [{info.title}]({info.url})" if info else f"- `{path.name}`")
    st.caption(f"{chunk_count} fragmentos indexados")

    if config.PUBLIC_DEMO:
        st.caption("Subir tus propios PDFs está disponible al ejecutar el proyecto en local o en Codespaces.")
    else:
        uploaded = st.file_uploader("Añade tu propio PDF", type="pdf")
        if uploaded is not None and st.session_state.get("last_upload") != uploaded.name:
            if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"El PDF supera {MAX_UPLOAD_MB} MB.")
            else:
                safe_name = re.sub(r"[^\w.\-]", "_", Path(uploaded.name).name)
                target = config.DATA_PATH / "uploads" / safe_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(uploaded.getbuffer())
                with st.spinner("Indexando los fragmentos nuevos…"):
                    result = build_database(download=False)
                st.session_state.last_upload = uploaded.name
                st.success(f"Añadidos {result.added} fragmentos. Los que ya existían no se han vuelto a procesar.")
                ensure_index.clear()
                st.rerun()

    st.divider()
    with st.expander("Cómo funciona"):
        st.markdown(
            f"- **Búsqueda:** {'híbrida (semántica + palabras clave, fusión RRF)' if config.RETRIEVAL_MODE == 'hybrid' else 'semántica'}, "
            f"top {config.TOP_K}\n"
            f"- **Umbral de relevancia:** {config.MIN_RELEVANCE:.2f} (si nada lo supera, no se llama al LLM)\n"
            f"- **LLM:** `{config.LLM_MODEL}` ({config.LLM_PROVIDER})\n"
            f"- **Embeddings:** `{config.EMBED_MODEL}` ({config.EMBEDDING_PROVIDER})\n"
            "- **Base vectorial:** ChromaDB"
        )
    st.markdown("[Código en GitHub](https://github.com/mmartinezvaras/Python-RAG-AI-para-los-PDFs)")

# ---------- Question ----------
st.write("**Prueba un ejemplo:**")
cols = st.columns(2)
for i, q in enumerate(EXAMPLES):
    cols[i % 2].button(q, key=f"ex{i}", on_click=set_question, args=(q,), use_container_width=True)

question = st.text_input("O escribe tu pregunta (español o inglés):", key="question")

if question:
    asked = st.session_state.setdefault("asked", 0)
    if config.PUBLIC_DEMO and asked >= config.MAX_QUESTIONS_PER_SESSION:
        st.info("Has llegado al límite de preguntas de la demo pública. ¡Gracias por probarla!")
        st.stop()
    st.session_state.asked = asked + 1

    st.subheader("Respuesta")
    placeholder = st.empty()
    try:
        with st.spinner("Buscando en los documentos…"):
            answer, pieces = stream_answer(question)
        text = ""
        for piece in pieces:
            text += piece
            placeholder.markdown(render_citations(text) + "▌")
        placeholder.markdown(render_citations(answer.text or text))
    except Exception as exc:  # show a friendly message instead of a stack trace
        st.error(f"Algo ha fallado: {exc}")
        st.stop()

    if not answer.grounded:
        st.caption(
            f"Ningún fragmento era lo bastante relevante (similitud máxima {answer.best_relevance:.2f} "
            f"< umbral {config.MIN_RELEVANCE:.2f}), así que no se ha llamado al modelo para no inventar."
        )
    else:
        st.subheader("Fuentes")
        cited = [p.number for p in answer.cited]
        ordered = sorted(answer.passages, key=lambda p: (p.number not in cited, p.number))
        for p in ordered:
            mark = "✅ " if p.number in cited else ""
            label = f"{mark}[{p.number}] {passage_label(p)} · relevancia {p.relevance:.2f}"
            with st.expander(label, expanded=p.number == (cited[0] if cited else None)):
                st.text(p.text)
                link = page_link(p.source, p.page)
                if link:
                    st.markdown(f"[Abrir el PDF oficial en esta página ↗]({link})")
        if not cited:
            st.caption("El modelo no ha citado ningún fragmento concreto; revisa las fuentes recuperadas.")
