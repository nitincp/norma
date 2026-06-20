"""
CAI Gate node — Constitutional AI validation of Gherkin + NFR artefacts.

Three assertions must pass before the artefact is emitted:
  1. Structural parse (non-LLM): Feature keyword + Scenario + Given/When/Then present.
  2. NFR structural check (non-LLM): all five required NFR sections present.
  3. LLM rubric (cloud/claude-sonnet): coverage of time-of-day greeting, both content
     choices (quote / joke), and at least one error path.

On failure the node appends feedback to gate_feedback and increments revision_count.
Use route_after_gate() as the LangGraph conditional-edge router.

Max revisions: 2 (after 2 failures the pipeline halts with gate_passed=False).
Langfuse span: cai_gate
"""

import re

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState

MODEL = settings.NORMA_CAI_GATE_MODEL
MAX_REVISIONS = 2

_RUBRIC_SYSTEM = (
    "You are a strict QA gatekeeper evaluating a Gherkin feature file.\n"
    "Check that the feature file covers ALL of the following requirements:\n"
    "  1. A time-of-day greeting (e.g. Good Morning / Good Afternoon / Good Evening).\n"
    "  2. Both content choices: Quote of the Day AND Joke of the Day.\n"
    "  3. At least one error or failure path (e.g. retrieval failure, graceful error message).\n\n"
    "Reply with exactly one of:\n"
    "  PASS\n"
    "  FAIL: <concise explanation of which requirement(s) are missing or inadequately covered>\n\n"
    "No other output."
)


def _assertion_1_structural(gherkin: str) -> tuple[bool, str]:
    """Non-LLM check: must have Feature, at least one Scenario, and Given/When/Then."""
    if not re.search(r"^\s*Feature:", gherkin, re.MULTILINE):
        return False, "Missing 'Feature:' keyword."
    if not re.search(r"^\s*Scenario", gherkin, re.MULTILINE):
        return False, "No Scenario or Scenario Outline blocks found."
    if not re.search(r"^\s*(Given|When|Then)", gherkin, re.MULTILINE):
        return False, "No Given/When/Then steps found."
    return True, ""


_NFR_REQUIRED_SECTIONS = [
    "## Tech Stack",
    "## External APIs",
    "## Timeouts & Retries",
    "## Auth Model",
    "## Error Handling",
]


def _assertion_2_nfr_structural(nfr: str) -> tuple[bool, str]:
    """Non-LLM check: NFR doc must contain all five required section headings."""
    missing = [s for s in _NFR_REQUIRED_SECTIONS if s not in nfr]
    if missing:
        return False, f"NFR document missing sections: {', '.join(missing)}"
    return True, ""


def _assertion_3_rubric(gherkin: str, client: httpx.Client) -> tuple[bool, str]:
    """LLM rubric check via cloud/claude-sonnet."""
    resp = client.post(
        f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": _RUBRIC_SYSTEM},
                {"role": "user", "content": gherkin},
            ],
            "max_tokens": 256,
            "temperature": 0.0,
            "metadata": {
                "generation_name": "cai-gate-rubric-call",
                "tags": ["cai_gate", "norma"],
            },
        },
    )
    resp.raise_for_status()
    verdict = resp.json()["choices"][0]["message"]["content"].strip()
    if verdict.startswith("PASS"):
        return True, ""
    # Anything starting with FAIL (or unexpected) is treated as failure
    return False, verdict if verdict.startswith("FAIL:") else f"FAIL: {verdict}"


def cai_gate_node(state: NormaState) -> NormaState:
    gherkin = state.get("gherkin_content", "")
    nfr = state.get("nfr_content", "")
    revision_count = state.get("revision_count", 0)

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    with langfuse.start_as_current_observation(
        name="cai_gate",
        as_type="span",
        input={"revision_count": revision_count, "model": MODEL},
    ) as span:
        # Assertion 1 — Gherkin structural (no LLM call)
        a1_ok, a1_msg = _assertion_1_structural(gherkin)

        if not a1_ok:
            feedback = f"Gherkin structural check failed: {a1_msg}"
            span.update(output={"gate_passed": False, "feedback": feedback, "assertion": 1})
            langfuse.flush()
            return {
                **state,
                "gate_passed": False,
                "gate_feedback": feedback,
                "revision_count": revision_count + 1,
            }

        # Assertion 2 — NFR structural (no LLM call)
        a2_ok, a2_msg = _assertion_2_nfr_structural(nfr)

        if not a2_ok:
            feedback = f"NFR structural check failed: {a2_msg}"
            span.update(output={"gate_passed": False, "feedback": feedback, "assertion": 2})
            langfuse.flush()
            return {
                **state,
                "gate_passed": False,
                "gate_feedback": feedback,
                "revision_count": revision_count + 1,
            }

        # Assertion 3 — LLM rubric
        with httpx.Client(timeout=60.0) as client:
            a3_ok, a3_msg = _assertion_3_rubric(gherkin, client)

        if not a3_ok:
            feedback = f"Coverage rubric failed: {a3_msg}"
            span.update(output={"gate_passed": False, "feedback": feedback, "assertion": 3})
            langfuse.flush()
            return {
                **state,
                "gate_passed": False,
                "gate_feedback": feedback,
                "revision_count": revision_count + 1,
            }

        span.update(output={"gate_passed": True})

    langfuse.flush()
    return {
        **state,
        "gate_passed": True,
        "gate_feedback": "",
    }


def route_after_gate(state: NormaState) -> str:
    """
    LangGraph conditional-edge router for use after cai_gate_node.

    Returns:
        "end"             — gate passed; pipeline continues to output
        "revise"          — gate failed and revisions remain; loop back to gherkin_specialist
        "halt"            — gate failed and max revisions exhausted; stop pipeline
    """
    if state.get("gate_passed"):
        return "end"
    if state.get("revision_count", 0) < MAX_REVISIONS:
        return "revise"
    return "halt"
