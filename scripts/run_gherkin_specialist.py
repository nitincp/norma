"""
Run the Gherkin Specialist node against REQ-001 and print the result.

Feeds a pre-baked normalised requirement so this smoke test can run
independently of the intake node.

Usage:
    python scripts/run_gherkin_specialist.py
"""

import sys

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph.gherkin_specialist import gherkin_specialist_node
from norma.graph.state import NormaState

# Pre-baked intake output for REQ-001 (avoids a cloud call just to smoke T2)
NORMALISED_REQ_001 = (
    "The application greets the user with a time-appropriate salutation "
    "(Good Morning, Good Afternoon, or Good Evening) based on the current local time. "
    "It then asks whether the user wishes to receive a Quote of the Day or a Joke of the Day. "
    "The application retrieves the selected content from the relevant external service "
    "and displays it to the user. If retrieval fails, the application displays a friendly "
    "error message."
)


def main() -> None:
    print(f"LITELLM_BASE_URL  : {settings.LITELLM_BASE_URL}")
    print(f"LANGFUSE_HOST     : {settings.LANGFUSE_HOST}")
    print(f"NORMA_GHERKIN_MODEL: {settings.NORMA_GHERKIN_MODEL}")
    print(f"\nNormalised requirement:\n  {NORMALISED_REQ_001}\n")
    print("Running gherkin_specialist node...\n")

    state: NormaState = {
        "raw_requirement": "",
        "normalised_requirement": NORMALISED_REQ_001,
        "actors": [],
        "external_deps": [],
    }

    try:
        result = gherkin_specialist_node(state)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    gherkin = result.get("gherkin_content", "")

    print("─" * 60)
    print("GHERKIN OUTPUT:")
    print(gherkin)
    print("─" * 60)

    # Basic validity check: must start with Feature:
    if not gherkin.lstrip().startswith("Feature:"):
        print("\nFAIL: output does not start with 'Feature:' keyword", file=sys.stderr)
        sys.exit(1)

    scenario_count = gherkin.count("Scenario")
    print(f"\nPASS: {scenario_count} Scenario block(s) found")


if __name__ == "__main__":
    main()
