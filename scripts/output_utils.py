"""
Shared output helpers for Norma pipeline scripts.

All artefacts are written to a dated run folder:
  output/YYYY-MM-DD/HHMMSS/

Each script writes a run_summary.json alongside the artefacts.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


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

    def elapsed(self) -> float:
        return round(time.monotonic() - self._start, 1)
