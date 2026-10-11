#!/usr/bin/env bash
# One-shot setup used by GitHub Codespaces, CI and Linux machines:
#   1. installs the Python dependencies
#   2. installs Ollama if it isn't there and starts it
#   3. downloads the LLM and the embedding model
#   4. indexes the PDFs in data/
set -euo pipefail
cd "$(dirname "$0")/.."

LLM_MODEL="${RAG_LLM_MODEL:-llama3.2:3b}"
EMBED_MODEL="${RAG_EMBED_MODEL:-nomic-embed-text}"

echo "▶ Installing Python dependencies"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

if ! command -v ollama >/dev/null 2>&1; then
  echo "▶ Installing Ollama"
  if ! command -v zstd >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq zstd >/dev/null
  fi
  curl -fsSL https://ollama.com/install.sh | sh
fi

bash scripts/start_ollama.sh

echo "▶ Downloading models ($EMBED_MODEL, $LLM_MODEL), this takes a few minutes the first time"
ollama pull "$EMBED_MODEL"
ollama pull "$LLM_MODEL"

echo "▶ Indexing the PDFs"
python populate_database.py

echo "✅ Setup complete. Run: streamlit run app.py"
