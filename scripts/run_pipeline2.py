"""
Pipeline 2 smoke test — Technical Layer.

Reads Pipeline 1 artefacts from the most recent dated run folder
(or a specific path via --run-dir), auto-selects rank-1 environment,
then runs:

  spec_advisor → Send(spec_specialist) × N
               → technical_gherkin_specialist → stage2_gate

Artefacts written to the same dated folder (or a new one if run standalone):
  req_001.technical.feature  — standalone @technical Gherkin
  req_001.<key>.md / .yaml   — spec artefacts
  run_summary.debug.json     — updated with Pipeline 2 results

Usage:
    uv run python scripts/run_pipeline2.py
    uv run python scripts/run_pipeline2.py --run-dir output/2026-06-20/123456
"""

import json
import sys
from pathlib import Path

from output_utils import Timer, make_run_dir, write_summary

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph import build_pipeline2
from norma.graph.state import EnvironmentOption, NormaState

RAW_REQUIREMENT = (
    "Generate application to greet user with proper time like Good Morning, Evening. "
    "And ask if he/she want to see Quote of the Day or Joke of the Day. And Reply."
)


def _find_latest_run_dir() -> Path | None:
    base = Path("output")
    if not base.exists():
        return None
    runs = sorted(base.glob("????-??-??/??????"), reverse=True)
    for r in runs:
        if (r / "req_001.feature").exists() and (r / "req_001.environments.checkpoint.json").exists():
            return r
    return None


def _load_p1_outputs(run_dir: Path) -> tuple[str, EnvironmentOption]:
    feature = run_dir / "req_001.feature"
    env_file = run_dir / "req_001.environments.checkpoint.json"

    if not feature.exists() or not env_file.exists():
        print(
            f"ERROR: Pipeline 1 artefacts not found in {run_dir}. "
            "Run run_pipeline1.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    environments: list[EnvironmentOption] = json.loads(env_file.read_text())
    if not environments:
        print("ERROR: No environment options in req_001.environments.checkpoint.json.", file=sys.stderr)
        sys.exit(1)

    return feature.read_text(), min(environments, key=lambda e: e["rank"])


def main() -> None:
    # Resolve run dir
    run_dir_arg = None
    if "--run-dir" in sys.argv:
        idx = sys.argv.index("--run-dir")
        if idx + 1 < len(sys.argv):
            run_dir_arg = Path(sys.argv[idx + 1])

    if run_dir_arg:
        run_dir = run_dir_arg
    else:
        run_dir = _find_latest_run_dir() or make_run_dir()

    timer = Timer()
    gherkin_business, selected_env = _load_p1_outputs(run_dir)

    initial: NormaState = {
        "raw_requirement": RAW_REQUIREMENT,
        "normalised_requirement": RAW_REQUIREMENT,
        "actors": [],
        "external_deps": [],
        "gherkin_business": gherkin_business,
        "selected_environment": selected_env,
        "spec_artefacts": {},
        "revision_count": 0,
    }

    pipeline2 = build_pipeline2()

    try:
        result: NormaState = pipeline2.invoke(initial)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    passed = result.get("gate_passed", False)
    advice = result.get("spec_advice") or []
    spec_artefacts = result.get("spec_artefacts") or {}
    gherkin_technical = result.get("gherkin_technical", "")

    # Write artefacts
    (run_dir / "req_001.technical.feature").write_text(gherkin_technical)
    for key, content in spec_artefacts.items():
        ext = "yaml" if key in ("openapi", "asyncapi") else "md"
        (run_dir / f"req_001.{key}.{ext}").write_text(content)

    written = ["req_001.technical.feature"] + [
        f"req_001.{k}.{'yaml' if k in ('openapi','asyncapi') else 'md'}"
        for k in spec_artefacts
    ]
    write_summary(run_dir, {
        "pipeline": "pipeline2",
        "gate_passed": passed,
        "gate_feedback": result.get("gate_feedback") or "",
        "revision_count": result.get("revision_count", 0),
        "specialist_count": len(advice),
        "specialists": [r["artefact_key"] for r in advice],
        "artefacts": written,
        "selected_environment": (
            f"{selected_env['runtime']} / {selected_env['framework']}"
        ),
        "wall_time_s": timer.elapsed(),
        "models": {
            "spec_advisor": settings.NORMA_SPEC_ADVISOR_MODEL,
            "tech_gherkin": settings.NORMA_TECH_GHERKIN_MODEL,
            "stage2_gate": settings.NORMA_STAGE2_GATE_MODEL,
        },
    })

    # Console — summary only
    status = "PASS" if passed else "FAIL"
    print(f"[Pipeline 2] {status} — {timer.elapsed()}s — {run_dir}/")
    print(f"  env: {selected_env['runtime']} / {selected_env['framework']}")
    print(f"  specialists: {[r['artefact_key'] for r in advice] or '(none)'}")
    print(f"  artefacts: {', '.join(written)}")
    if not passed:
        print(f"  feedback: {result.get('gate_feedback')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
