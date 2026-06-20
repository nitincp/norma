"""
End-to-end two-stage pipeline (REQ-004).

Pipeline 1 — Business Layer:
  intake → [gherkin_specialist ‖ environment_advisor] → stage1_gate

Pipeline 2 — Technical Layer (harness auto-selects rank-1 environment):
  spec_advisor → Send(spec_specialist) × N
               → technical_gherkin_specialist → stage2_gate

Artefacts written to output/YYYY-MM-DD/HHMMSS/:
  req_001.feature            — business Gherkin (SME layer)
  req_001.environments.json  — ranked environment options
  req_001.technical.feature  — standalone @technical Gherkin (dev/QA layer)
  req_001.<key>.md / .yaml   — spec artefacts from specialist(s)
  run_summary.json           — combined gate results, models, wall time

Console: one summary line per stage + final artefact list.

Usage:
    uv run python scripts/run_full.py
"""

import json
import sys

from output_utils import Timer, make_run_dir, write_summary

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph import build_pipeline2, pipeline1
from norma.graph.state import EnvironmentOption, NormaState

RAW_REQUIREMENT = (
    "Generate application to greet user with proper time like Good Morning, Evening. "
    "And ask if he/she want to see Quote of the Day or Joke of the Day. And Reply."
)


def main() -> None:
    total_timer = Timer()
    run_dir = make_run_dir()

    # ── Pipeline 1 ────────────────────────────────────────────────────────────
    p1_timer = Timer()
    p1_initial: NormaState = {
        "raw_requirement": RAW_REQUIREMENT,
        "normalised_requirement": "",
        "actors": [],
        "external_deps": [],
    }

    try:
        p1: NormaState = pipeline1.invoke(p1_initial)
    except Exception as exc:
        print(f"ERROR (Pipeline 1): {exc}", file=sys.stderr)
        sys.exit(1)

    p1_passed = p1.get("stage1_passed", False)
    env_options = p1.get("environment_options") or []
    gherkin_business = p1.get("gherkin_business") or p1.get("gherkin_content", "")

    # Write P1 artefacts
    (run_dir / "req_001.feature").write_text(gherkin_business)
    (run_dir / "req_001.environments.json").write_text(
        json.dumps(env_options, indent=2)
    )

    p1_status = "PASS" if p1_passed else "FAIL"
    print(
        f"[P1 Business]  {p1_status} — {p1_timer.elapsed()}s"
        f" — env options: {len(env_options)}"
    )

    if not p1_passed:
        write_summary(run_dir, {
            "stage1_passed": False,
            "stage1_feedback": p1.get("stage1_feedback") or "",
            "wall_time_s": total_timer.elapsed(),
        })
        print(f"  feedback: {p1.get('stage1_feedback')}", file=sys.stderr)
        sys.exit(1)

    # SME environment selection — harness picks rank-1
    selected_env: EnvironmentOption = min(env_options, key=lambda e: e["rank"])
    print(
        f"  env selected: [{selected_env['rank']}] "
        f"{selected_env['runtime']} / {selected_env['framework']}"
    )

    # ── Pipeline 2 ────────────────────────────────────────────────────────────
    p2_timer = Timer()
    p2_initial: NormaState = {
        "raw_requirement": RAW_REQUIREMENT,
        "normalised_requirement": p1.get("normalised_requirement", RAW_REQUIREMENT),
        "actors": p1.get("actors") or [],
        "external_deps": p1.get("external_deps") or [],
        "gherkin_business": gherkin_business,
        "selected_environment": selected_env,
        "spec_artefacts": {},
        "revision_count": 0,
    }

    pipeline2 = build_pipeline2()

    try:
        p2: NormaState = pipeline2.invoke(p2_initial)
    except Exception as exc:
        print(f"ERROR (Pipeline 2): {exc}", file=sys.stderr)
        sys.exit(1)

    p2_passed = p2.get("gate_passed", False)
    advice = p2.get("spec_advice") or []
    spec_artefacts = p2.get("spec_artefacts") or {}
    gherkin_technical = p2.get("gherkin_technical", "")

    # Write P2 artefacts
    (run_dir / "req_001.technical.feature").write_text(gherkin_technical)
    for key, content in spec_artefacts.items():
        ext = "yaml" if key in ("openapi", "asyncapi") else "md"
        (run_dir / f"req_001.{key}.{ext}").write_text(content)

    p2_status = "PASS" if p2_passed else "FAIL"
    print(
        f"[P2 Technical] {p2_status} — {p2_timer.elapsed()}s"
        f" — specialists: {[r['artefact_key'] for r in advice] or '(none)'}"
    )

    # run_summary.json — combined
    all_artefacts = (
        ["req_001.feature", "req_001.environments.json", "req_001.technical.feature"]
        + [
            f"req_001.{k}.{'yaml' if k in ('openapi','asyncapi') else 'md'}"
            for k in spec_artefacts
        ]
    )
    write_summary(run_dir, {
        "stage1_passed": p1_passed,
        "stage2_passed": p2_passed,
        "stage2_feedback": p2.get("gate_feedback") or "",
        "revision_count": p2.get("revision_count", 0),
        "specialist_count": len(advice),
        "specialists": [r["artefact_key"] for r in advice],
        "selected_environment": (
            f"{selected_env['runtime']} / {selected_env['framework']}"
        ),
        "artefacts": all_artefacts,
        "wall_time_s": total_timer.elapsed(),
        "models": {
            "gherkin": settings.NORMA_GHERKIN_MODEL,
            "env_advisor": settings.NORMA_ENV_ADVISOR_MODEL,
            "stage1_gate": settings.NORMA_STAGE1_GATE_MODEL,
            "spec_advisor": settings.NORMA_SPEC_ADVISOR_MODEL,
            "tech_gherkin": settings.NORMA_TECH_GHERKIN_MODEL,
            "stage2_gate": settings.NORMA_STAGE2_GATE_MODEL,
        },
    })

    # Final console summary
    print(f"\nTotal: {total_timer.elapsed()}s — {run_dir}/")
    for f in all_artefacts:
        print(f"  {run_dir / f}")

    if not p2_passed:
        print(f"\nfeedback: {p2.get('gate_feedback')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
