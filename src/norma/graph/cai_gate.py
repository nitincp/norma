"""
CAI Gate node — Constitutional AI validation of all pipeline artefacts.

Assertions:
  1. Gherkin structural (non-LLM): Feature + Scenario + Given/When/Then present.
  2. RFC 2119 structural (non-LLM): if rfc2119 artefact present, must contain
     '# Constraints' heading and at least one RFC keyword (MUST/SHOULD/MAY).
  3. LLM rubric (cloud/claude-sonnet): coverage check on Gherkin content.

Assertion 2 fires only when the rfc2119 artefact is in spec_artefacts — the gate
adapts to whatever specialists ran. Add new artefact assertions here as new
specialists are registered.

On failure: appends to gate_feedback, increments revision_count.
Max revisions: 2 — after 2 failures the pipeline halts with gate_passed=False.
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

_RFC_KEYWORDS = re.compile(r"\b(MUST NOT|SHOULD NOT|MUST|SHOULD|MAY)\b")


def _assertion_1_gherkin_structural(gherkin: str) -> tuple[bool, str]:
    """Non-LLM: Feature keyword + at least one Scenario + Given/When/Then."""
    if not re.search(r"^\s*Feature:", gherkin, re.MULTILINE):
        return False, "Missing 'Feature:' keyword."
    if not re.search(r"^\s*Scenario", gherkin, re.MULTILINE):
        return False, "No Scenario or Scenario Outline blocks found."
    if not re.search(r"^\s*(Given|When|Then)", gherkin, re.MULTILINE):
        return False, "No Given/When/Then steps found."
    return True, ""


def _assertion_2_rfc2119_structural(rfc: str) -> tuple[bool, str]:
    """Non-LLM: RFC 2119 doc must have '# Constraints' and at least one RFC keyword."""
    if "# Constraints" not in rfc:
        return False, "RFC 2119 artefact missing '# Constraints' heading."
    if not _RFC_KEYWORDS.search(rfc):
        return False, "RFC 2119 artefact contains no MUST/SHOULD/MAY keywords."
    return True, ""


def _assertion_3_rubric(
    gherkin: str,
    client: httpx.Client,
    trace_id: str | None = None,
    parent_observation_id: str | None = None,
) -> tuple[bool, str]:
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
                "trace_id": trace_id,
                "parent_observation_id": parent_observation_id,
            },
        },
    )
    resp.raise_for_status()
    verdict = resp.json()["choices"][0]["message"]["content"].strip()
    if verdict.startswith("PASS"):
        return True, ""
    return False, verdict if verdict.startswith("FAIL:") else f"FAIL: {verdict}"


def cai_gate_node(state: NormaState) -> NormaState:
    gherkin = state.get("gherkin_content", "")
    spec_artefacts = state.get("spec_artefacts") or {}
    revision_count = state.get("revision_count", 0)

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    def _fail(msg: str, assertion: int) -> NormaState:
        span.update(output={"gate_passed": False, "feedback": msg, "assertion": assertion})
        langfuse.flush()
        return {
            "gate_passed": False,
            "gate_feedback": msg,
            "revision_count": revision_count + 1,
        }

    with langfuse.start_as_current_observation(
        name="cai_gate",
        as_type="span",
        input={
            "revision_count": revision_count,
            "model": MODEL,
            "artefacts_present": list(spec_artefacts.keys()),
        },
    ) as span:
        # Assertion 1 — Gherkin structural
        ok, msg = _assertion_1_gherkin_structural(gherkin)
        if not ok:
            return _fail(f"Gherkin structural check failed: {msg}", 1)

        # Assertion 2 — RFC 2119 structural (only if the artefact was produced)
        if "rfc2119" in spec_artefacts:
            ok, msg = _assertion_2_rfc2119_structural(spec_artefacts["rfc2119"])
            if not ok:
                return _fail(f"RFC 2119 structural check failed: {msg}", 2)

        # Assertion 3 — LLM rubric on Gherkin
        with httpx.Client(timeout=60.0) as client:
            ok, msg = _assertion_3_rubric(
                gherkin, client,
                trace_id=langfuse.get_current_trace_id(),
                parent_observation_id=langfuse.get_current_observation_id(),
            )
        if not ok:
            return _fail(f"Coverage rubric failed: {msg}", 3)

        span.update(output={"gate_passed": True})

    langfuse.flush()
    return {"gate_passed": True, "gate_feedback": ""}


def route_after_gate(state: NormaState) -> str:
    """
    LangGraph conditional-edge router after cai_gate_node.

    Returns:
        "end"   — gate passed
        "revise" — gate failed, revisions remain; loop back to gherkin_specialist
        "halt"   — gate failed, max revisions exhausted
    """
    if state.get("gate_passed"):
        return "end"
    if state.get("revision_count", 0) < MAX_REVISIONS:
        return "revise"
    return "halt"
