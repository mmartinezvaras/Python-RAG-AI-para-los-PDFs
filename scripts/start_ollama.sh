#!/usr/bin/env bash
# Starts the Ollama server in the background if it isn't already running.
set -euo pipefail

if curl -sf http://localhost:11434/api/tags >/dev/null; then
  exit 0
fi

echo "▶ Starting Ollama"
nohup ollama serve >/tmp/ollama.log 2>&1 &

for _ in $(seq 1 60); do
  if curl -sf http://localhost:11434/api/tags >/dev/null; then
    exit 0
  fi
  sleep 1
done

echo "❌ Ollama did not start, see /tmp/ollama.log" >&2
exit 1
