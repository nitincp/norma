"""
Run the intake node against REQ-001 and print the result.

Usage:
    python scripts/run_intake.py
"""

import json
import sys

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph.intake import intake_node
from norma.graph.state import NormaState

REQ_001 = (
    "Generate application to greet user with proper time like Good Morning, Evening. "
    "And ask if he/she want to see Quote of the Day or Joke of the Day. And Reply."
)


def main() -> None:
    print(f"LITELLM_BASE_URL : {settings.LITELLM_BASE_URL}")
    print(f"LANGFUSE_HOST    : {settings.LANGFUSE_HOST}")
    print(f"\nRaw requirement:\n  {REQ_001}\n")
    print("Running intake node...\n")

    state: NormaState = {"raw_requirement": REQ_001}

    try:
        result = intake_node(state)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print("─" * 60)
    print("NORMALISED REQUIREMENT:")
    print(result.get("normalised_requirement", "<empty>"))
    print()
    print("ACTORS:")
    for a in result.get("actors", []):
        print(f"  - {a}")
    print()
    print("EXTERNAL DEPS:")
    for d in result.get("external_deps", []):
        print(f"  - {d}")
    print("─" * 60)
    print("\nFull state (JSON):")
    print(json.dumps({k: v for k, v in result.items()}, indent=2))


if __name__ == "__main__":
    main()
