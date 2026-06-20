"""
Spec Advisor standalone smoke test — REQ-003.

Runs spec_advisor_node in isolation with the REQ-001 normalised requirement
and prints the advice list. Verifies that rfc2119 is recommended.

Usage:
    uv run python scripts/run_spec_advisor.py
"""

import sys

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph.spec_advisor import spec_advisor_node
from norma.graph.state import NormaState

NORMALISED = (
    "A conversational app that greets the user based on time of day "
    "(Good Morning / Good Afternoon / Good Evening) and lets them choose between "
    "Quote of the Day or Joke of the Day, fetched from external APIs. "
    "The app must handle API unavailability gracefully and respond within 2 seconds."
)

state: NormaState = {
    "raw_requirement": "Build a greeting app with quotes and jokes.",
    "normalised_requirement": NORMALISED,
    "actors": ["user"],
    "external_deps": ["ZenQuotes API", "JokeAPI"],
}

print("Running Spec Advisor...")
print(f"Input: {NORMALISED[:80]}...")
print()

result = spec_advisor_node(state)
advice = result.get("spec_advice", [])

print(f"Spec Advisor recommended {len(advice)} specialist(s):")
for rec in advice:
    deps = f" (after: {rec['depends_on']})" if rec["depends_on"] else ""
    print(f"  [{rec['language']}]{deps}: {rec['rationale']}")

print()

# Smoke test assertion
languages = {rec["language"] for rec in advice}
if "rfc2119" not in languages:
    print("FAIL — rfc2119 not recommended; the requirement implies constraints")
    sys.exit(1)

print("PASS — rfc2119 recommended as expected")
