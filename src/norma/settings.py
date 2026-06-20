"""
Runtime configuration — reads from env (populated by docker-compose env_file or
a local .env via python-dotenv). Import this module first in any script that
might run outside the devcontainer so .env is always loaded.
"""

from pathlib import Path

from dotenv import load_dotenv

# Walk up from this file to find the repo root .env.
# Works whether the package is installed editable or not.
_repo_root = Path(__file__).resolve().parents[2]
load_dotenv(_repo_root / ".env", override=False)  # env already set by docker wins

import os  # noqa: E402  (must come after load_dotenv)


def _require(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"Required env var {key!r} is not set. Check your .env file.")
    return v


# ── Langfuse ──────────────────────────────────────────────────────────────────
LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://langfuse-web:3000")
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")

# ── LiteLLM ───────────────────────────────────────────────────────────────────
LITELLM_BASE_URL: str = os.getenv("LITELLM_BASE_URL", "http://litellm-gateway:4000")
LITELLM_MASTER_KEY: str = os.getenv("LITELLM_MASTER_KEY", "")

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://host-gateway:11434")

# ── Norma model aliases ───────────────────────────────────────────────────────
NORMA_DEFAULT_MODEL: str = os.getenv("NORMA_DEFAULT_MODEL", "cloud/claude-sonnet")
NORMA_GHERKIN_MODEL: str = os.getenv("NORMA_GHERKIN_MODEL", "cloud/claude-sonnet")
NORMA_NFR_MODEL: str = os.getenv("NORMA_NFR_MODEL", "cloud/claude-sonnet")
NORMA_SPEC_ADVISOR_MODEL: str = os.getenv("NORMA_SPEC_ADVISOR_MODEL", "cloud/claude-sonnet")
NORMA_CAI_GATE_MODEL: str = os.getenv("NORMA_CAI_GATE_MODEL", "cloud/claude-sonnet")
NORMA_VALIDATION_MODEL: str = os.getenv("NORMA_VALIDATION_MODEL", "local/qwen2.5-1.5b")
NORMA_DEEP_MODEL: str = os.getenv("NORMA_DEEP_MODEL", "local/qwen2.5-1.5b")
