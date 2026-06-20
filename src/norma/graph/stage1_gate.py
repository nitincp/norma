"""
Stage 1 Gate — validates Pipeline 1 output before SME handoff.

Assertions:
  1. Environment plausibility (non-LLM): at least one EnvironmentOption present.
  2. Gherkin business coverage (LLM rubric): does gherkin_business cover
     all key behaviours mentioned in the normalised requirement?

On pass: copies gherkin_content → gherkin_business (immutable handoff key).
On fail: sets stage1_passed=False with feedback; Pipeline 1 halts (no retry loop
         — a failed Stage 1 requires prompt-level intervention, not a re-run).

Langfuse span: stage1_gate
"""

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState

MODEL = settings.NORMA_STAGE1_GATE_MODEL

_RUBRIC_SYSTEM = (
    "You are a business analyst reviewing a Gherkin feature file against a requirement.\n"
    "Decide whether the Gherkin captures all the NAMED FEATURES described in the requirement "
    "at a high level. Do NOT require boundary/edge-case scenarios, implementation details, "
    "or exhaustive examples — those belong in technical specs.\n\n"
    "Key behaviours to look for: named user actions, named system responses, "
    "named content types, and named error flows that the requirement explicitly states.\n\n"
    "Output ONLY one of these two forms — nothing else, no reasoning, no markdown:\n"
    "  PASS\n"
    "  FAIL: <one sentence naming which named feature is entirely absent from the Gherkin>\n"
)


def _assertion_1_env_plausibility(state: NormaState) -> tuple[bool, str]:
    """Non-LLM: at least one environment option must be present."""
    options = state.get("environment_options") or []
    if not options:
        return False, "Environment Advisor produced no options."
    return True, ""


def _assertion_2_gherkin_coverage(
    normalised: str,
    gherkin: str,
    client: httpx.Client,
    trace_id: str | None = None,
    parent_observation_id: str | None = None,
) -> tuple[bool, str]:
    """LLM rubric: does Gherkin cover all behaviours in the normalised requirement?"""
    user_msg = (
        f"## Requirement\n{normalised}\n\n"
        f"## Gherkin\n{gherkin}"
    )
    resp = client.post(
        f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": _RUBRIC_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 512,
            "temperature": 0.0,
            "metadata": {
                "generation_name": "stage1-gate-rubric-call",
                "tags": ["stage1_gate", "norma"],
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


def stage1_gate_node(state: NormaState) -> NormaState:
    gherkin = state.get("gherkin_content", "")
    normalised = state.get("normalised_requirement", "")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    with langfuse.start_as_current_observation(
        name="stage1_gate",
        as_type="span",
        input={
            "model": MODEL,
            "env_option_count": len(state.get("environment_options") or []),
        },
    ) as span:
        # Assertion 1 — environment plausibility (non-LLM)
        ok, msg = _assertion_1_env_plausibility(state)
        if not ok:
            span.update(output={"stage1_passed": False, "feedback": msg, "assertion": 1})
            langfuse.flush()
            return {"stage1_passed": False, "stage1_feedback": msg}

        # Assertion 2 — Gherkin business coverage (LLM)
        with httpx.Client(timeout=60.0) as client:
            ok, msg = _assertion_2_gherkin_coverage(
                normalised, gherkin, client,
                trace_id=langfuse.get_current_trace_id(),
                parent_observation_id=langfuse.get_current_observation_id(),
            )
        if not ok:
            feedback = f"Gherkin coverage check failed: {msg}"
            span.update(output={"stage1_passed": False, "feedback": feedback, "assertion": 2})
            langfuse.flush()
            return {"stage1_passed": False, "stage1_feedback": feedback}

        span.update(output={"stage1_passed": True})

    langfuse.flush()
    # Promote gherkin_content to gherkin_business (immutable in Pipeline 2)
    return {
        "stage1_passed": True,
        "stage1_feedback": "",
        "gherkin_business": gherkin,
    }
