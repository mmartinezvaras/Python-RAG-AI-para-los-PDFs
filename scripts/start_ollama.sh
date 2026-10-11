#!/usr/bin/env bash
# Starts the Ollama server in the background if it isn't already running.
set -euo pipefail

LOG=/tmp/ollama.log

if curl -sf http://localhost:11434/api/tags >/dev/null; then
  exit 0
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "❌ Ollama is not installed. Run: bash scripts/setup.sh" >&2
  exit 1
fi

echo "▶ Starting Ollama"
# setsid detaches the server from this shell so it keeps running after the script exits.
setsid nohup ollama serve >"$LOG" 2>&1 < /dev/null 9>&- &
echo $! > /tmp/ollama-started-by-script.pid

for _ in $(seq 1 120); do
  if curl -sf http://localhost:11434/api/tags >/dev/null; then
    echo "✅ Ollama is running"
    exit 0
  fi
  sleep 1
done

echo "❌ Ollama did not start. Last lines of $LOG:" >&2
tail -20 "$LOG" >&2 || true
exit 1
