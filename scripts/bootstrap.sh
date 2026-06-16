#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Python version check ───────────────────────────────────────────────────────
PYTHON=$(command -v python3.12 || command -v python3 || true)
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: python3 not found. Install Python 3.12+." >&2
  exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(printf '%s\n' "3.12" "$PY_VERSION" | sort -V | head -1)" != "3.12" ]]; then
  echo "ERROR: Python 3.12+ required, found $PY_VERSION." >&2
  exit 1
fi

echo "Using $PYTHON ($PY_VERSION)"

# ── Virtual environment ────────────────────────────────────────────────────────
VENV="$REPO_ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment at $VENV …"
  "$PYTHON" -m venv "$VENV"
fi

source "$VENV/bin/activate"

# ── Install package ────────────────────────────────────────────────────────────
echo "Installing norma (editable) + dev dependencies …"
pip install --quiet --upgrade pip
pip install --quiet -e "$REPO_ROOT[dev]"

# ── .env check ────────────────────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "WARNING: .env not found. Copy .env.example and fill in secrets:"
  echo "  cp .env.example .env"
  echo "Skipping connectivity checks."
  exit 0
fi

# ── Connectivity checks ────────────────────────────────────────────────────────
echo "Running connectivity checks …"
python "$REPO_ROOT/scripts/test_langfuse.py"
python "$REPO_ROOT/scripts/test_litellm.py"

echo ""
echo "Bootstrap complete. Activate the venv with:"
echo "  source .venv/bin/activate"
