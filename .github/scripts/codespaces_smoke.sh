#!/usr/bin/env bash
# Runs inside the real Codespaces dev container (after postCreateCommand),
# simulating a visitor: kill anything left from setup, start the demo the way
# postAttachCommand does, and check the web app and an answer.
set -uo pipefail

notice() { echo "::$1 title=$2::$(echo "$3" | tail -c 1500 | sed ':a;N;$!ba;s/\n/%0A/g')"; }

# A fresh Codespace session doesn't keep the Ollama process from setup.
pkill -f "ollama serve" || true
sleep 2

nohup bash scripts/run_app.sh > /tmp/app.log 2>&1 &

for _ in $(seq 1 300); do
  if curl -sf http://localhost:8501/_stcore/health >/dev/null; then break; fi
  sleep 2
done

if ! curl -sf http://localhost:8501/_stcore/health >/dev/null; then
  notice error "demo did not start" "$(cat /tmp/app.log; echo ---; tail -20 /tmp/ollama.log 2>/dev/null)"
  exit 1
fi

answer=$(python query_data.py "How many points does the winner of a Formula One race get?" 2>&1)
echo "$answer"
if ! echo "$answer" | grep -qiE "\b25\b|twenty-five"; then
  notice error "wrong answer" "$answer"
  exit 1
fi
notice notice "Codespaces demo OK" "$(head -5 /tmp/app.log) | $answer"
