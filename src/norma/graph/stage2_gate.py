"""
Stage 2 Gate — validates Pipeline 2 output before final artefact emission.

Assertions:
  1. Spec structural checks (non-LLM, per artefact type):
       - Gherkin technical: Feature + Scenario + Given/When/Then present.
       - RFC 2119: '# Constraints' heading + at least one RFC keyword.
       (Add new artefact assertions here as new specialists are registered.)
  2. Technical Gherkin coverage (LLM rubric): does gherkin_technical contain
     at least one @technical scenario and reference constraints from spec artefacts?

On failure: appends to gate_feedback, increments revision_count.
Max revisions: 2 — after 2 failures the pipeline halts with gate_passed=False.
On pass: sets gate_passed=True.

Langfuse span: stage2_gate
"""

import re

import httpx
from langfuse import Langfuse, propagate_attributes

from norma import settings
from norma.graph.state import NormaState

MODEL = settings.NORMA_STAGE2_GATE_MODEL
MAX_REVISIONS = 2

_RFC_KEYWORDS = re.compile(r"\b(MUST NOT|SHOULD NOT|MUST|SHOULD|MAY)\b")

_LANGFUSE_PROMPT_NAME = "norma.stage2_gate.rubric"
_PROMPT_CACHE_TTL = 300  # seconds


def _assertion_1_gherkin_technical_structural(gherkin: str) -> tuple[bool, str]:
    """Non-LLM: Feature + at least one Scenario + Given/When/Then."""
    if not re.search(r"^\s*Feature:", gherkin, re.MULTILINE):
        return False, "Technical Gherkin missing 'Feature:' keyword."
    if not re.search(r"^\s*Scenario", gherkin, re.MULTILINE):
        return False, "Technical Gherkin has no Scenario blocks."
    if not re.search(r"^\s*(Given|When|Then)", gherkin, re.MULTILINE):
        return False, "Technical Gherkin has no Given/When/Then steps."
    return True, ""


def _assertion_1_rfc2119_structural(rfc: str) -> tuple[bool, str]:
    """Non-LLM: RFC 2119 doc must have '# Constraints' + at least one RFC keyword."""
    if "# Constraints" not in rfc:
        return False, "RFC 2119 artefact missing '# Constraints' heading."
    if not _RFC_KEYWORDS.search(rfc):
        return False, "RFC 2119 artefact contains no MUST/SHOULD/MAY keywords."
    return True, ""


def _assertion_2_technical_gherkin_coverage(
    gherkin_technical: str,
    spec_artefacts: dict[str, str],
    client: httpx.Client,
    rubric_system: str,
    trace_id: str | None = None,
    parent_observation_id: str | None = None,
) -> tuple[bool, str]:
    """LLM rubric: do @technical scenarios cover spec constraints?"""
    artefact_block = "\n\n".join(
        f"### {key.upper()}\n{content}" for key, content in spec_artefacts.items()
    ) or "(no spec artefacts)"

    user_msg = (
        f"## Technical Gherkin\n{gherkin_technical}\n\n"
        f"## Spec Artefacts\n{artefact_block}"
    )
    resp = client.post(
        f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": rubric_system},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 300,
            "temperature": 0.0,
            "metadata": {
                "generation_name": "stage2-gate-rubric-call",
                "tags": ["stage2_gate", "norma"],
                "existing_trace_id": trace_id,
                "parent_observation_id": parent_observation_id,
            },
        },
    )
    resp.raise_for_status()
    verdict = resp.json()["choices"][0]["message"]["content"].strip()
    if verdict.startswith("PASS"):
        return True, ""
    return False, verdict if verdict.startswith("FAIL:") else f"FAIL: {verdict}"


def stage2_gate_node(state: NormaState) -> NormaState:
    gherkin_technical = state.get("gherkin_technical", "")
    spec_artefacts = state.get("spec_artefacts") or {}
    revision_count = state.get("revision_count", 0)
    session_id = state.get("session_id")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    rubric_system = langfuse.get_prompt(
        _LANGFUSE_PROMPT_NAME, cache_ttl_seconds=_PROMPT_CACHE_TTL
    ).prompt

    with propagate_attributes(session_id=session_id):
        with langfuse.start_as_current_observation(
            name="stage2_gate",
            as_type="span",
            input={
                "revision_count": revision_count,
                "model": MODEL,
                "artefacts_present": list(spec_artefacts.keys()),
            },
        ) as span:
            def _fail(msg: str, assertion: int) -> NormaState:
                span.update(output={"gate_passed": False, "feedback": msg, "assertion": assertion})
                langfuse.flush()
                return {
                    "gate_passed": False,
                    "gate_feedback": msg,
                    "revision_count": revision_count + 1,
                }

            # Assertion 1a — technical Gherkin structural
            ok, msg = _assertion_1_gherkin_technical_structural(gherkin_technical)
            if not ok:
                return _fail(f"Technical Gherkin structural check failed: {msg}", 1)

            # Assertion 1b — RFC 2119 structural (only if artefact was produced)
            if "rfc2119" in spec_artefacts:
                ok, msg = _assertion_1_rfc2119_structural(spec_artefacts["rfc2119"])
                if not ok:
                    return _fail(f"RFC 2119 structural check failed: {msg}", 1)

            # Assertion 2 — LLM rubric: technical Gherkin covers spec constraints
            with httpx.Client(timeout=60.0) as client:
                ok, msg = _assertion_2_technical_gherkin_coverage(
                    gherkin_technical, spec_artefacts, client, rubric_system,
                    trace_id=langfuse.get_current_trace_id(),
                    parent_observation_id=langfuse.get_current_observation_id(),
                )
            if not ok:
                return _fail(f"Technical Gherkin coverage rubric failed: {msg}", 2)

            span.update(output={"gate_passed": True})

    langfuse.flush()
    return {"gate_passed": True, "gate_feedback": ""}


def route_after_stage2(state: NormaState) -> str:
    """
    LangGraph conditional-edge router after stage2_gate_node.

    Returns:
        "end"    — gate passed
        "revise" — gate failed, revisions remain; loop back to technical_gherkin_specialist
        "halt"   — gate failed, max revisions exhausted
    """
    if state.get("gate_passed"):
        return "end"
    if state.get("revision_count", 0) < MAX_REVISIONS:
        return "revise"
    return "halt"
