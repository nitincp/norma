"""
NFR Specialist standalone smoke test — REQ-002.

Runs the nfr_specialist_node in isolation with canned Gherkin input and
prints the resulting NFR document. Does not invoke the full pipeline.

Usage:
    uv run python scripts/run_nfr_specialist.py
"""

import sys

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph.nfr_specialist import nfr_specialist_node
from norma.graph.state import NormaState

NORMALISED = (
    "A conversational app that greets the user based on time of day "
    "(Good Morning / Good Afternoon / Good Evening) and lets them choose between "
    "Quote of the Day or Joke of the Day, fetched from external APIs."
)

GHERKIN = """\
Feature: Greeting and daily content app
  Background:
    Given the app is running

  Scenario Outline: Time-of-day greeting
    Given the current time is <time>
    When the user opens the app
    Then they see <greeting>

    Examples:
      | time  | greeting          |
      | 08:00 | Good Morning      |
      | 14:00 | Good Afternoon    |
      | 20:00 | Good Evening      |

  Scenario: User requests Quote of the Day
    Given the user sees the greeting
    When the user chooses "Quote of the Day"
    Then the app fetches a quote from the external API
    And displays it to the user

  Scenario: User requests Joke of the Day
    Given the user sees the greeting
    When the user chooses "Joke of the Day"
    Then the app fetches a joke from the external API
    And displays it to the user

  Scenario: External API is unavailable
    Given the external API is down
    When the user requests content
    Then the app displays a graceful error message
    And does not crash
"""


def main() -> None:
    print(f"LITELLM_BASE_URL : {settings.LITELLM_BASE_URL}")
    print(f"NORMA_NFR_MODEL  : {settings.NORMA_NFR_MODEL}")
    print()

    state: NormaState = {
        "raw_requirement": (
            "Generate application to greet user with proper time like Good Morning, Evening. "
            "And ask if he/she want to see Quote of the Day or Joke of the Day. And Reply."
        ),
        "normalised_requirement": NORMALISED,
        "actors": ["user"],
        "external_deps": ["Quote API", "Joke API"],
        "gherkin_content": GHERKIN,
    }

    try:
        result = nfr_specialist_node(state)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    nfr = result.get("nfr_content", "")
    print("── NFR DOCUMENT ──────────────────────────────────────────────────────")
    print(nfr)
    print()

    required_sections = [
        "## Tech Stack",
        "## External APIs",
        "## Timeouts & Retries",
        "## Auth Model",
        "## Error Handling",
    ]
    missing = [s for s in required_sections if s not in nfr]
    if missing:
        print(f"FAIL — missing sections: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    print("PASS — all 5 NFR sections present")


if __name__ == "__main__":
    main()
