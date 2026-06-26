"""
A/B test — run the full two-stage pipeline with three model configurations
in sequence and compare results.

Variants:
  sonnet   — cloud/claude-sonnet   (baseline)
  gemini   — cloud/gemini-flash    (cost-optimised)
  grok     — cloud/grok            (cost-optimised)

Each variant gets its own dated run folder. A comparison report is written to
  output/ab/<date>/<time>/ab_report.md

Usage:
    uv run python scripts/run_ab_test.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# All per-node model env vars
_MODEL_KEYS = [
    "NORMA_GHERKIN_MODEL",
    "NORMA_ENV_ADVISOR_MODEL",
    "NORMA_SPEC_ADVISOR_MODEL",
    "NORMA_STAGE1_GATE_MODEL",
    "NORMA_STAGE2_GATE_MODEL",
    "NORMA_TECH_GHERKIN_MODEL",
]

VARIANTS: list[tuple[str, str]] = [
    ("sonnet", "cloud/claude-sonnet"),
    ("gemini", "cloud/gemini-flash"),
    ("grok", "cloud/grok"),
]


def _run_variant(label: str, model: str) -> dict:
    """Run run_full.py with all nodes set to *model*. Returns parsed result dict."""
    env = os.environ.copy()
    for key in _MODEL_KEYS:
        env[key] = model

    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "scripts/run_full.py"],
        env=env,
        capture_output=True,
        text=True,
    )
    wall = round(time.monotonic() - start, 1)

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    # Find the run dir from the "Total: Xs — output/..." line
    run_dir: Path | None = None
    for line in stdout.splitlines():
        if line.startswith("Total:") and "output/" in line:
            parts = line.split(" — ")
            if len(parts) >= 2:
                run_dir = Path(parts[-1].strip())

    # Load run_summary.json if available
    summary: dict = {}
    if run_dir and (run_dir / "run_summary.debug.json").exists():
        summary = json.loads((run_dir / "run_summary.debug.json").read_text())

    return {
        "label": label,
        "model": model,
        "returncode": proc.returncode,
        "wall_s": wall,
        "stdout": stdout,
        "stderr": stderr,
        "run_dir": str(run_dir) if run_dir else None,
        "stage1_passed": summary.get("stage1_passed"),
        "stage2_passed": summary.get("stage2_passed"),
        "specialists": summary.get("specialists", []),
        "specialist_count": summary.get("specialist_count", 0),
        "selected_environment": summary.get("selected_environment"),
        "revision_count": summary.get("revision_count", 0),
        "stage2_feedback": summary.get("stage2_feedback", ""),
        "artefacts": summary.get("artefacts", []),
    }


def _status(r: dict) -> str:
    p1 = "✓" if r["stage1_passed"] else "✗"
    p2 = "✓" if r["stage2_passed"] else "✗"
    ok = r["returncode"] == 0
    return f"{'PASS' if ok else 'FAIL'} (P1={p1} P2={p2})"


def _write_report(report_dir: Path, results: list[dict]) -> Path:
    now = datetime.now().isoformat(timespec="seconds")
    lines = [
        "# Norma A/B Test Report",
        f"\nRun: {now}\n",
        "## Summary\n",
        "| Variant | Model | Result | Wall time | Specialists | Env selected | Revisions |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        specs = ", ".join(r["specialists"]) or "(none)"
        env = r["selected_environment"] or "—"
        lines.append(
            f"| {r['label']} | `{r['model']}` | {_status(r)} "
            f"| {r['wall_s']}s | {specs} | {env} | {r['revision_count']} |"
        )

    lines.append("\n## Console output per variant\n")
    for r in results:
        lines.append(f"### {r['label']} (`{r['model']}`)\n")
        lines.append(f"**Run dir:** `{r['run_dir'] or 'not found'}`\n")
        if r["stdout"]:
            lines.append("```")
            lines.append(r["stdout"])
            lines.append("```")
        if r["stderr"]:
            lines.append("\n**stderr:**")
            lines.append("```")
            lines.append(r["stderr"])
            lines.append("```")
        lines.append("")

    path = report_dir / "ab_report.md"
    path.write_text("\n".join(lines))
    return path


def main() -> None:
    now = datetime.now()
    report_dir = Path("output") / "ab" / now.strftime("%Y-%m-%d") / now.strftime("%H%M%S")
    report_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for label, model in VARIANTS:
        print(f"[AB] Running {label} ({model}) …", flush=True)
        r = _run_variant(label, model)
        results.append(r)
        print(f"[AB] {label}: {_status(r)} — {r['wall_s']}s", flush=True)

    report_path = _write_report(report_dir, results)

    print(f"\nReport: {report_path}")
    print("\n| Variant | Result | Time | Specialists |")
    print("|---|---|---|---|")
    for r in results:
        specs = ", ".join(r["specialists"]) or "(none)"
        print(f"| {r['label']} | {_status(r)} | {r['wall_s']}s | {specs} |")

    # Exit non-zero only if ALL variants failed
    if all(r["returncode"] != 0 for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
