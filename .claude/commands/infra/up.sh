#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# ── Ollama ────────────────────────────────────────────────────────────────────
echo "Ensuring Ollama is running..."
if ! pgrep -x ollama > /dev/null; then
  ollama serve &>/dev/null &
  echo "  Started ollama serve (background)"
  sleep 2
else
  echo "  Ollama already running"
fi

OLLAMA_MODELS=(
  "qwen2.5:0.5b"
  "phi3:mini"
)

for model in "${OLLAMA_MODELS[@]}"; do
  echo "  Pulling $model (skipped if already present)..."
  ollama pull "$model"
done

# ── Docker services ───────────────────────────────────────────────────────────
echo ""
echo "Starting infra..."
docker compose -f "$REPO_ROOT/docker/langfuse-compose.yml" --env-file "$REPO_ROOT/.env" up -d

echo ""
echo "Services:"
echo "  Ollama       → http://localhost:11434"
echo "  Langfuse UI  → http://localhost:3000"
echo "  LiteLLM      → http://localhost:4000"
echo "  ClickHouse   → http://localhost:8123"
