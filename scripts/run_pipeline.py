"""
End-to-end pipeline smoke test — REQ-001 input through REQ-003 pipeline.

Runs: intake → (gherkin_specialist ‖ spec_advisor → spec_specialist(s)) → cai_gate
On success, writes artefacts to output/specs/req_001/:
  req_001.feature          — validated Gherkin
  req_001.<key>.md / .yaml — dynamic spec artefacts from spec_specialist(s)

Usage:
    uv run python scripts/run_pipeline.py
"""

import sys
from pathlib import Path

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph import pipeline
from norma.graph.state import NormaState

RAW_REQUIREMENT = (
    "Generate application to greet user with proper time like Good Morning, Evening. "
    "And ask if he/she want to see Quote of the Day or Joke of the Day. And Reply."
)


def main() -> None:
    print(f"LITELLM_BASE_URL       : {settings.LITELLM_BASE_URL}")
    print(f"LANGFUSE_HOST          : {settings.LANGFUSE_HOST}")
    print(f"NORMA_DEFAULT_MODEL    : {settings.NORMA_DEFAULT_MODEL}")
    print(f"NORMA_GHERKIN_MODEL    : {settings.NORMA_GHERKIN_MODEL}")
    print(f"NORMA_SPEC_ADVISOR_MODEL: {settings.NORMA_SPEC_ADVISOR_MODEL}")
    print(f"NORMA_CAI_GATE_MODEL   : {settings.NORMA_CAI_GATE_MODEL}")
    print()

    initial: NormaState = {
        "raw_requirement": RAW_REQUIREMENT,
        "normalised_requirement": "",
        "actors": [],
        "external_deps": [],
        "revision_count": 0,
    }

    try:
        result: NormaState = pipeline.invoke(initial)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print("── INTAKE ────────────────────────────────────────────────────────────")
    print(f"normalised : {result.get('normalised_requirement', '')[:200]}")
    print(f"actors     : {result.get('actors')}")
    print(f"ext_deps   : {result.get('external_deps')}")
    print()

    print("── SPEC ADVISOR ──────────────────────────────────────────────────────")
    advice = result.get("spec_advice") or []
    if advice:
        for rec in advice:
            deps = f" (after: {rec['depends_on']})" if rec["depends_on"] else ""
            print(f"  [{rec['artefact_key']}]{deps}: {rec['rationale']}")
    else:
        print("  (no specialist advice — Gherkin-only bundle)")
    print()

    print("── CAI GATE ──────────────────────────────────────────────────────────")
    print(f"gate_passed    : {result.get('gate_passed')}")
    print(f"revision_count : {result.get('revision_count', 0)}")
    print(f"gate_feedback  : {result.get('gate_feedback') or '(none)'}")
    print()

    if not result.get("gate_passed"):
        print("HALT — gate did not pass after max revisions", file=sys.stderr)
        sys.exit(1)

    out_dir = Path("output/specs/req_001")
    out_dir.mkdir(parents=True, exist_ok=True)

    gherkin = result.get("gherkin_content", "")
    (out_dir / "req_001.feature").write_text(gherkin)

    spec_artefacts = result.get("spec_artefacts") or {}
    for key, content in spec_artefacts.items():
        ext = "yaml" if key in ("openapi", "asyncapi") else "md"
        (out_dir / f"req_001.{key}.{ext}").write_text(content)

    written = ["req_001.feature"] + [
        f"req_001.{k}.{'yaml' if k in ('openapi','asyncapi') else 'md'}"
        for k in spec_artefacts
    ]
    print(f"PASS — {len(written)} artefact(s) written to {out_dir}/")
    for f in written:
        print(f"  {out_dir / f}")
    print()

    print("── GHERKIN ───────────────────────────────────────────────────────────")
    print(gherkin)

    for key, content in spec_artefacts.items():
        print()
        print(f"── {key.upper()} ARTEFACT ────────────────────────────────────────────")
        print(content)


if __name__ == "__main__":
    main()
