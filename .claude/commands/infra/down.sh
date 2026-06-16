#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Stopping infra..."
docker compose -f "$REPO_ROOT/docker/langfuse-compose.yml" --env-file "$REPO_ROOT/.env" down
