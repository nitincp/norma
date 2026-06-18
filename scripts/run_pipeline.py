"""
End-to-end pipeline smoke test — REQ-001.

Runs intake → gherkin_specialist → cai_gate and prints the final state.
On success, writes the validated .feature file to output/req_001.feature.

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
    print(f"LITELLM_BASE_URL    : {settings.LITELLM_BASE_URL}")
    print(f"LANGFUSE_HOST       : {settings.LANGFUSE_HOST}")
    print(f"NORMA_DEFAULT_MODEL : {settings.NORMA_DEFAULT_MODEL}")
    print(f"NORMA_GHERKIN_MODEL : {settings.NORMA_GHERKIN_MODEL}")
    print(f"NORMA_CAI_GATE_MODEL: {settings.NORMA_CAI_GATE_MODEL}")
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

    print("── INTAKE OUTPUT ─────────────────────────────────────────────────────")
    print(f"normalised_requirement: {result.get('normalised_requirement', '')[:200]}")
    print(f"actors                : {result.get('actors')}")
    print(f"external_deps         : {result.get('external_deps')}")
    print()
    print("── CAI GATE RESULT ───────────────────────────────────────────────────")
    print(f"gate_passed    : {result.get('gate_passed')}")
    print(f"revision_count : {result.get('revision_count', 0)}")
    print(f"gate_feedback  : {result.get('gate_feedback') or '(none)'}")
    print()

    gherkin = result.get("gherkin_content", "")
    if result.get("gate_passed"):
        out_path = Path("output/req_001.feature")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(gherkin)
        print(f"PASS — validated .feature written to {out_path}")
        print()
        print(gherkin)
    else:
        print("HALT — gate did not pass after max revisions", file=sys.stderr)
        print()
        print(gherkin, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
