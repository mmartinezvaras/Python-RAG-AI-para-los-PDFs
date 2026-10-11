#!/usr/bin/env bash
# Makes sure everything is installed and Ollama is running, then launches the
# web demo on port 8501. Safe to run at any time: if the first-time setup hasn't
# finished (or failed), it waits for it or runs it again.
set -euo pipefail
cd "$(dirname "$0")/.."

# setup.sh is idempotent and takes a lock, so this waits for a setup that is
# still running and finishes anything missing (Ollama, models, index).
bash scripts/setup.sh

bash scripts/start_ollama.sh

echo "▶ Starting the web demo on port 8501"
exec python -m streamlit run app.py \
  --server.headless true \
  --server.port 8501 \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false \
  --client.toolbarMode minimal
