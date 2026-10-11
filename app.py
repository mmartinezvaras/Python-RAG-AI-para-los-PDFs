"""Web demo: ask questions about the PDFs and see the cited sources.

Run with:  streamlit run app.py
"""

import json
import os
import urllib.request

import streamlit as st

from get_embedding_function import EMBEDDING_PROVIDER, OLLAMA_EMBED_MODEL
from populate_database import CHROMA_PATH, DATA_PATH, build_database
from query_data import LLM_MODEL, answer_question

OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = f"http://{OLLAMA_URL}"

EXAMPLES = [
    "How many points does the winner of a Formula One race get?",
    "What material are F1 drivers' overalls made of?",
    "Where did modern association football originate?",
    "¿Cada cuánto se celebra el Mundial de la FIFA?",
    "Who won the 2018 Tour de France?",  # not in the PDFs -> should say it doesn't know
]

st.set_page_config(page_title="RAG over PDFs", page_icon="📄", layout="centered")


def ollama_models() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as resp:
            return [m["name"] for m in json.load(resp).get("models", [])]
    except Exception:
        return None


def has_model(installed: list[str], name: str) -> bool:
    return any(m == name or m == f"{name}:latest" for m in installed)


def pdf_files() -> list[str]:
    return sorted(f for f in os.listdir(DATA_PATH) if f.lower().endswith(".pdf"))


@st.cache_resource(show_spinner="Indexing the PDFs for the first time…")
def ensure_index() -> bool:
    if not os.path.isdir(CHROMA_PATH) or not os.listdir(CHROMA_PATH):
        build_database()
    return True


def set_question(q: str):
    st.session_state.question = q


# ---------- Header ----------
st.title("📄 Ask your PDFs")
st.caption(
    "Retrieval-Augmented Generation: the answer is generated **only** from passages "
    "retrieved from the documents, and every answer cites the exact file, page and chunk."
)

# ---------- Health checks ----------
installed = ollama_models()
if installed is None:
    st.error(
        f"Can't reach Ollama at `{OLLAMA_URL}`. Start it with `ollama serve` "
        "(in GitHub Codespaces it starts automatically, give it a few seconds and reload)."
    )
    st.stop()

needed = [LLM_MODEL] + ([OLLAMA_EMBED_MODEL] if EMBEDDING_PROVIDER == "ollama" else [])
missing = [m for m in needed if not has_model(installed, m)]
if missing:
    st.warning(
        "Downloading models, this only happens once: "
        + ", ".join(f"`{m}`" for m in missing)
        + ". Run `ollama pull <model>` if it doesn't finish on its own, then reload."
    )
    st.stop()

ensure_index()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Documents")
    for f in pdf_files():
        st.markdown(f"- `{f}`")

    uploaded = st.file_uploader("Add your own PDF", type="pdf")
    if uploaded is not None and st.session_state.get("last_upload") != uploaded.name:
        with open(os.path.join(DATA_PATH, os.path.basename(uploaded.name)), "wb") as fh:
            fh.write(uploaded.getbuffer())
        with st.spinner("Indexing new chunks…"):
            added = build_database()
        st.session_state.last_upload = uploaded.name
        st.success(f"Added {added} new chunks. Existing chunks were not re-embedded.")
        st.rerun()

    st.divider()
    st.markdown(
        f"**LLM:** `{LLM_MODEL}` (Ollama, local)  \n"
        f"**Embeddings:** `{OLLAMA_EMBED_MODEL if EMBEDDING_PROVIDER == 'ollama' else 'AWS Bedrock'}`  \n"
        "**Vector store:** ChromaDB"
    )
    st.markdown("[Source code on GitHub](https://github.com/mmartinezvaras/Python-RAG-AI-para-los-PDFs)")

# ---------- Question ----------
st.write("**Try an example:**")
cols = st.columns(2)
for i, q in enumerate(EXAMPLES):
    cols[i % 2].button(q, key=f"ex{i}", on_click=set_question, args=(q,), use_container_width=True)

question = st.text_input("Or type your own question (English or Spanish):", key="question")

if question:
    with st.spinner("Searching the documents and generating the answer…"):
        try:
            answer = answer_question(question)
        except Exception as exc:  # show a friendly message instead of a stack trace
            st.error(f"Something went wrong: {exc}")
            st.stop()

    st.subheader("Answer")
    st.write(answer.text)

    st.subheader("Sources")
    for source, passage in zip(answer.sources, answer.passages):
        file_, page, chunk = (source or "?:?:?").rsplit(":", 2)
        label = f"{os.path.basename(file_)} · page {int(page) + 1 if page.isdigit() else page} · chunk {chunk}"
        with st.expander(label):
            st.text(passage)
