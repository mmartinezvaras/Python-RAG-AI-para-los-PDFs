#!/usr/bin/env bash
# One-shot setup used by GitHub Codespaces, CI and Linux machines:
#   1. installs the Python dependencies
#   2. installs Ollama if it isn't there and starts it
#   3. downloads the LLM and the embedding model
#   4. indexes the PDFs in data/
set -euo pipefail
cd "$(dirname "$0")/.."

# Only one setup at a time: a second run waits for the first, then just checks
# that everything is in place (every step below is safe to repeat).
exec 9>/tmp/rag-setup.lock
if ! flock -n 9; then
  echo "⏳ First-time setup is still running (installing the AI model). Waiting for it to finish…"
  flock 9
fi

LLM_MODEL="${RAG_LLM_MODEL:-llama3.2:3b}"
EMBED_MODEL="${RAG_EMBED_MODEL:-nomic-embed-text}"

echo "▶ Installing Python dependencies"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

if ! command -v ollama >/dev/null 2>&1; then
  echo "▶ Installing Ollama"
  if ! command -v zstd >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    # The dev container image ships a Yarn apt source with an expired key that
    # makes `apt-get update` fail; we don't need it, so drop it first.
    sudo rm -f /etc/apt/sources.list.d/yarn.list
    sudo apt-get update -qq || true
    sudo apt-get install -y -qq zstd >/dev/null
  fi
  if ! command -v zstd >/dev/null 2>&1; then
    echo "❌ zstd is required to install Ollama. Install it (e.g. sudo apt-get install zstd) and re-run." >&2
    exit 1
  fi
  curl -fsSL https://ollama.com/install.sh | sh
fi

bash scripts/start_ollama.sh

for model in "$EMBED_MODEL" "$LLM_MODEL"; do
  if ! ollama show "$model" >/dev/null 2>&1; then
    echo "▶ Downloading model $model (only the first time, a few minutes)"
    ollama pull "$model"
  fi
done

echo "▶ Indexing the PDFs"
python populate_database.py

echo "✅ Setup complete. Run: streamlit run app.py"
