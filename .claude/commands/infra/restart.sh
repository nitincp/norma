#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="docker compose -f $REPO_ROOT/docker/langfuse-compose.yml --env-file $REPO_ROOT/.env"

# If a service name is passed, restart just that one; otherwise restart all.
if [[ $# -gt 0 ]]; then
  echo "Restarting $*..."
  $COMPOSE restart "$@"
else
  echo "Restarting all infra services..."
  $COMPOSE restart
fi
