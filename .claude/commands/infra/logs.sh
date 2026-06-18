#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

# Pass a service name to tail just that one, e.g.: ./infra-logs.sh langfuse-web
docker compose -f "$REPO_ROOT/docker/langfuse-compose.yml" --env-file "$REPO_ROOT/.env" logs -f --tail=100 "$@"
