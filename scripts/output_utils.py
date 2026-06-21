"""
Shared output helpers for Norma pipeline scripts.

All artefacts are written to a dated run folder:
  output/YYYY-MM-DD/HHMMSS/

Each script writes a run_summary.json alongside the artefacts.
"""

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


def make_run_dir(base: str = "output") -> Path:
    """Return a timestamped run directory (created on first call)."""
    now = datetime.now()
    run_dir = Path(base) / now.strftime("%Y-%m-%d") / now.strftime("%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_summary(run_dir: Path, summary: dict[str, Any]) -> Path:
    """Write run_summary.json into run_dir; return its path."""
    summary["timestamp"] = datetime.now().isoformat()
    path = run_dir / "run_summary.json"
    path.write_text(json.dumps(summary, indent=2))
    return path


class Timer:
    """Simple wall-clock timer."""

    def __init__(self) -> None:
        self._start = time.monotonic()
        self.start_utc = datetime.now(timezone.utc)

    def elapsed(self) -> float:
        return round(time.monotonic() - self._start, 1)


def fetch_run_usage(
    start_utc: datetime,
    end_utc: datetime,
    langfuse_host: str,
    public_key: str,
    secret_key: str,
) -> dict[str, Any]:
    """
    Query Langfuse for token usage and cost across all observations in the given
    time window. Returns {"prompt_tokens": int, "completion_tokens": int, "cost_usd": float}.

    Sums only observations with token usage > 0 (i.e. actual LLM calls).
    Paginates until all observations in the window are fetched.
    """
    creds = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}"}
    from_ts = start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_ts = end_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    prompt_tokens = 0
    completion_tokens = 0
    cost_usd = 0.0
    page = 1

    with httpx.Client(timeout=15.0) as client:
        while True:
            r = client.get(
                f"{langfuse_host}/api/public/observations",
                headers=headers,
                params={"fromStartTime": from_ts, "toStartTime": to_ts, "limit": 50, "page": page},
            )
            r.raise_for_status()
            data = r.json()
            observations = data.get("data", [])
            if not observations:
                break
            for obs in observations:
                usage = obs.get("usage") or {}
                total = usage.get("total", 0) or 0
                if total > 0:
                    prompt_tokens += usage.get("input", 0) or 0
                    completion_tokens += usage.get("output", 0) or 0
                    cost_usd += obs.get("calculatedTotalCost") or 0.0
            if len(observations) < 50:
                break
            page += 1

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost_usd, 6),
    }
