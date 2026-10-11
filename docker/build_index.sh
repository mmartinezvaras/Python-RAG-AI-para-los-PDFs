#!/usr/bin/env bash
# Build step: download the models and index the PDFs into the image.
set -euo pipefail

ollama serve >/tmp/ollama.log 2>&1 &
OLLAMA_PID=$!
for _ in $(seq 1 60); do
  curl -sf http://localhost:11434/api/tags >/dev/null && break
  sleep 1
done

ollama pull "${RAG_EMBED_MODEL:-nomic-embed-text}"
ollama pull "${RAG_LLM_MODEL:-llama3.2:3b}"
python populate_database.py --reset

kill "$OLLAMA_PID"
wait "$OLLAMA_PID" 2>/dev/null || true
