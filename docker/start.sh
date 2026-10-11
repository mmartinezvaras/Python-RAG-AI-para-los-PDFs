#!/usr/bin/env bash
# Container entrypoint: start Ollama, warm up the model, then serve the web demo.
set -euo pipefail

ollama serve >/tmp/ollama.log 2>&1 &
for _ in $(seq 1 60); do
  curl -sf http://localhost:11434/api/tags >/dev/null && break
  sleep 1
done

# Load the model into memory in the background so the first question is quicker.
(curl -s http://localhost:11434/api/generate \
  -d "{\"model\": \"${RAG_LLM_MODEL:-llama3.2:3b}\", \"prompt\": \"hi\", \"stream\": false}" >/dev/null || true) &

exec python -m streamlit run app.py \
  --server.headless true \
  --server.address 0.0.0.0 \
  --server.port "${PORT:-7860}" \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false \
  --client.toolbarMode minimal
