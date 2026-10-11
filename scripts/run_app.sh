#!/usr/bin/env bash
# Makes sure Ollama is running, then launches the web demo on port 8501.
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/start_ollama.sh

exec streamlit run app.py \
  --server.headless true \
  --server.port 8501 \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false
