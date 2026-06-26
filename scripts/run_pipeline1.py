"""
Pipeline 1 smoke test — Business Layer.

Runs: intake → [gherkin_specialist ‖ environment_advisor] → stage1_gate

Artefacts written to output/YYYY-MM-DD/HHMMSS/:
  req_001.feature           — business Gherkin
  req_001.environments.checkpoint.json — ranked environment options
  run_summary.debug.json          — gate result, model config, wall time

Usage:
    uv run python scripts/run_pipeline1.py
"""

import json
import sys

from output_utils import Timer, make_run_dir, write_summary

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph import pipeline1
from norma.graph.state import NormaState

RAW_REQUIREMENT = (
    "Generate application to greet user with proper time like Good Morning, Evening. "
    "And ask if he/she want to see Quote of the Day or Joke of the Day. And Reply."
)


def main() -> None:
    timer = Timer()
    run_dir = make_run_dir()

    initial: NormaState = {
        "raw_requirement": RAW_REQUIREMENT,
        "normalised_requirement": "",
        "actors": [],
        "external_deps": [],
    }

    try:
        result: NormaState = pipeline1.invoke(initial)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    passed = result.get("stage1_passed", False)
    env_options = result.get("environment_options") or []
    gherkin = result.get("gherkin_business") or result.get("gherkin_content", "")

    # Write artefacts
    (run_dir / "req_001.feature").write_text(gherkin)
    (run_dir / "req_001.environments.checkpoint.json").write_text(
        json.dumps(env_options, indent=2)
    )
    write_summary(run_dir, {
        "pipeline": "pipeline1",
        "stage1_passed": passed,
        "stage1_feedback": result.get("stage1_feedback") or "",
        "env_option_count": len(env_options),
        "selected_env_rank1": (
            f"{env_options[0]['runtime']} / {env_options[0]['framework']}"
            if env_options else None
        ),
        "wall_time_s": timer.elapsed(),
        "models": {
            "gherkin": settings.NORMA_GHERKIN_MODEL,
            "env_advisor": settings.NORMA_ENV_ADVISOR_MODEL,
            "stage1_gate": settings.NORMA_STAGE1_GATE_MODEL,
        },
    })

    # Console — summary only
    status = "PASS" if passed else "FAIL"
    print(f"[Pipeline 1] {status} — {timer.elapsed()}s — {run_dir}/")
    for opt in env_options:
        print(f"  env [{opt['rank']}] {opt['runtime']} / {opt['framework']}")
    if not passed:
        print(f"  feedback: {result.get('stage1_feedback')}", file=sys.stderr)
        sys.exit(1)
    print("  artefacts: req_001.feature, req_001.environments.checkpoint.json, run_summary.debug.json")

    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
