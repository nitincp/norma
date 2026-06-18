#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── uv check ──────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
  echo "ERROR: uv not found. Install it with:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "uv $(uv --version)"

# ── Python 3.12 + virtualenv + dependencies ───────────────────────────────────
echo "Syncing environment (Python 3.12, all dev deps) …"
cd "$REPO_ROOT"
uv sync --extra dev

# ── .env check ────────────────────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo ""
  echo "WARNING: .env not found. Copy .env.example and fill in secrets:"
  echo "  cp .env.example .env"
  echo "Skipping connectivity checks."
  exit 0
fi

# ── Connectivity checks ────────────────────────────────────────────────────────
echo "Running connectivity checks …"
uv run python "$REPO_ROOT/scripts/test_langfuse.py"
uv run python "$REPO_ROOT/scripts/test_litellm.py"

echo ""
echo "Bootstrap complete. Run commands with:"
echo "  uv run python ..."
echo "  source .venv/bin/activate  (optional, for interactive use)"
