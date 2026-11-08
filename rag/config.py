"""All settings in one place. Every value can be overridden with an environment variable.

Two ready-made setups:

* Local (default): everything runs on Ollama, no accounts or API keys.
* Online demo: any OpenAI-compatible API (e.g. Google Gemini's free tier) for both the
  embeddings and the answers, so it can run on a free host without a GPU or Ollama:

      RAG_LLM_PROVIDER=openai  RAG_EMBEDDINGS=openai
      OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
      OPENAI_API_KEY=...       RAG_LLM_MODEL=<gemini chat model>  RAG_EMBED_MODEL=gemini-embedding-001
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = Path(os.getenv("RAG_DATA_PATH", BASE_DIR / "data"))
CHROMA_PATH = Path(os.getenv("RAG_CHROMA_PATH", BASE_DIR / "chroma"))
COLLECTION = "pdf_chunks"

# --- Models -------------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("RAG_LLM_PROVIDER", "ollama").lower()  # ollama | openai
EMBEDDING_PROVIDER = os.getenv("RAG_EMBEDDINGS", "ollama").lower()  # ollama | openai | bedrock

_default_llm = "llama3.2:3b" if LLM_PROVIDER == "ollama" else "gemini-3.8-flash"
_default_embed = "nomic-embed-text" if EMBEDDING_PROVIDER == "ollama" else "gemini-embedding-001"
LLM_MODEL = os.getenv("RAG_LLM_MODEL", _default_llm)
EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", _default_embed)
# A stronger model can grade the evaluation; defaults to the answering model.
JUDGE_MODEL = os.getenv("RAG_JUDGE_MODEL", LLM_MODEL)

OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = f"http://{OLLAMA_URL}"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Indexing -----------------------------------------------------------------------------
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))

# --- Retrieval ----------------------------------------------------------------------------
RETRIEVAL_MODE = os.getenv("RAG_RETRIEVAL", "hybrid").lower()  # hybrid | vector
TOP_K = int(os.getenv("RAG_TOP_K", "5"))
CANDIDATES = int(os.getenv("RAG_CANDIDATES", "20"))  # per retriever, before fusion
# Cosine similarity of the best passage below which we answer "not in the documents"
# without calling the LLM. Depends on the embedding model: calibrate it with eval/run_eval.py.
MIN_RELEVANCE = float(os.getenv("RAG_MIN_RELEVANCE", "0.45"))
# Language of the documents ("es" or "en"). Questions in the other language are translated
# before searching (embeddings and BM25 match much better within one language); the answer
# is still written in the question's language. Set it to "" to disable.
DOC_LANGUAGE = os.getenv("RAG_DOC_LANGUAGE", "es").lower()

# --- Web demo -----------------------------------------------------------------------------
PUBLIC_DEMO = os.getenv("RAG_PUBLIC_DEMO") == "1"
MAX_QUESTIONS_PER_SESSION = int(os.getenv("RAG_MAX_QUESTIONS", "25"))
