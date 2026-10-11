#!/usr/bin/env bash
# Runs inside the real Codespaces dev container (after postCreateCommand),
# simulating a visitor: start the demo the way postAttachCommand does and
# check the web app and an answer. Every phase has a time limit and reports
# what it saw as a GitHub annotation.
set -uo pipefail

note() { echo "::$1 title=$2::$(printf '%s' "$3" | tail -c 2000 | sed ':a;N;$!ba;s/\n/%0A/g')"; }
logs() { echo "--- app.log"; tail -40 /tmp/app.log 2>/dev/null; echo "--- ollama.log"; tail -15 /tmp/ollama.log 2>/dev/null; }

note notice "after postCreate" "ollama: $(command -v ollama || echo MISSING) | models: $(ls ~/.ollama/models/manifests/registry.ollama.ai/library 2>/dev/null | tr '\n' ' ') | chroma: $(ls chroma 2>/dev/null | wc -l) files | processes: $(pgrep -fa 'ollama|streamlit|setup.sh' | tr '\n' ';')"

# A fresh Codespace session doesn't keep the Ollama process from setup.
pkill -f "ollama serve" || true
sleep 2

setsid nohup bash scripts/run_app.sh > /tmp/app.log 2>&1 < /dev/null &

ok=0
for _ in $(seq 1 240); do   # up to 8 minutes
  if curl -sf http://localhost:8501/_stcore/health >/dev/null; then ok=1; break; fi
  sleep 2
done
if [ "$ok" != 1 ]; then
  note error "demo did not start in 8 min" "$(logs)"
  exit 1
fi
note notice "demo started" "$(logs)"

answer=$(timeout 300 python query_data.py "How many points does the winner of a Formula One race get?" 2>&1)
echo "$answer"
if ! echo "$answer" | grep -qiE "\b25\b|twenty-five"; then
  note error "wrong or no answer" "$answer"
  exit 1
fi
note notice "Codespaces demo OK" "$answer"

pkill -f "streamlit run" || true
pkill -f "ollama serve" || true
