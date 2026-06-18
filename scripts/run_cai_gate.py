"""
Run the CAI Gate node against a pre-baked Gherkin artefact and print the verdict.

Feeds a static .feature string so this smoke test can run independently of T1/T2.
To test the revision path, set FORCE_FAIL=1 to feed a deliberately broken artefact.

Usage:
    python scripts/run_cai_gate.py
    FORCE_FAIL=1 python scripts/run_cai_gate.py
"""

import os
import sys

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph.cai_gate import cai_gate_node, route_after_gate
from norma.graph.state import NormaState

SAMPLE_GHERKIN = """\
Feature: Greeting and Daily Content App

  Background:
    Given the application is running

  Scenario Outline: User receives a time-appropriate greeting
    Given the current time is <time>
    When the user opens the app
    Then the user sees "<greeting>"

    Examples:
      | time  | greeting       |
      | 07:00 | Good Morning   |
      | 13:00 | Good Afternoon |
      | 19:00 | Good Evening   |

  Scenario: User requests a Quote of the Day
    Given the user has been greeted
    When the user selects "Quote of the Day"
    Then the app retrieves a quote from the quote service
    And the user sees the quote displayed

  Scenario: User requests a Joke of the Day
    Given the user has been greeted
    When the user selects "Joke of the Day"
    Then the app retrieves a joke from the joke service
    And the user sees the joke displayed

  Scenario: External service is unavailable
    Given the user has been greeted
    And the external content service is unavailable
    When the user selects "Quote of the Day"
    Then the app displays a friendly error message
"""

BROKEN_GHERKIN = "This is not valid Gherkin at all."


def main() -> None:
    force_fail = os.getenv("FORCE_FAIL", "").strip() == "1"
    gherkin = BROKEN_GHERKIN if force_fail else SAMPLE_GHERKIN

    print(f"LITELLM_BASE_URL   : {settings.LITELLM_BASE_URL}")
    print(f"LANGFUSE_HOST      : {settings.LANGFUSE_HOST}")
    print(f"NORMA_CAI_GATE_MODEL: {settings.NORMA_CAI_GATE_MODEL}")
    print(f"Mode: {'FORCE_FAIL (broken Gherkin)' if force_fail else 'normal'}\n")

    state: NormaState = {
        "raw_requirement": "",
        "normalised_requirement": "",
        "actors": [],
        "external_deps": [],
        "gherkin_content": gherkin,
        "revision_count": 0,
    }

    try:
        result = cai_gate_node(state)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    route = route_after_gate(result)

    print(f"gate_passed    : {result.get('gate_passed')}")
    print(f"revision_count : {result.get('revision_count', 0)}")
    print(f"gate_feedback  : {result.get('gate_feedback') or '(none)'}")
    print(f"router decision: {route}")

    if result.get("gate_passed"):
        print("\nPASS: both assertions satisfied")
    else:
        print(f"\nFAIL: gate rejected artefact → router says '{route}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
