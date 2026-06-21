"""
Spec Advisor node — CRISPE-prompted per-requirement bundle planner.

Pipeline 2 inputs (REQ-004):
  - gherkin_business       — SME-validated business Gherkin (immutable)
  - selected_environment   — SME-chosen runtime/framework/deployment option
  - normalised_requirement — traceability; secondary signal

With validated Gherkin + an explicit environment, the Spec Advisor's inferences
collapse from three (environment + contracts + constraints) to one, improving
confidence and determinism.

Falls back to normalised_requirement alone when gherkin_business is absent
(backward compat for legacy pipeline smoke tests).

Prompt source: prompts/spec_advisor.yaml → seeded to Langfuse as norma.spec_advisor.
Edit the YAML and re-run scripts/seed_prompts.py to update the live prompt.

Model: NORMA_SPEC_ADVISOR_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: spec_advisor
"""

import json
import re

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState, SpecRecommendation

MODEL = settings.NORMA_SPEC_ADVISOR_MODEL

_LANGFUSE_PROMPT_NAME = "norma.spec_advisor"
_PROMPT_CACHE_TTL = 300  # seconds

_VALID_ARTEFACT_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def _parse_advice(text: str) -> list[SpecRecommendation]:
    """
    Parse the LLM JSON output into a list of SpecRecommendation dicts.
    Drops malformed entries; logs nothing — failures surface as an empty list
    (pipeline still runs Gherkin-only).
    """
    text = re.sub(r"```[a-z]*\n?", "", text).strip().rstrip("`").strip()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            raw = json.loads(m.group())
        except json.JSONDecodeError:
            return []

    advice: list[SpecRecommendation] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("artefact_key", "")).strip().lower()
        required = (
            "language", "artefact_key", "rationale",
            "requirement_segments", "role", "insight", "statement",
        )
        if not all(item.get(f) for f in required):
            continue
        if not _VALID_ARTEFACT_KEY.match(key):
            continue
        advice.append(
            SpecRecommendation(
                language=str(item["language"]),
                artefact_key=key,
                rationale=str(item["rationale"]),
                depends_on=[
                    str(d).strip().lower()
                    for d in item.get("depends_on", [])
                    if isinstance(d, str)
                ],
                requirement_segments=str(item["requirement_segments"]),
                role=str(item["role"]),
                insight=str(item["insight"]),
                statement=str(item["statement"]),
            )
        )
    return advice


def _build_user_message(state: NormaState) -> str:
    """
    Build the user message for the Spec Advisor.

    Pipeline 2 (REQ-004): uses gherkin_business + selected_environment as primary
    signal; appends normalised_requirement for traceability.
    Legacy / Pipeline 1 fallback: uses normalised_requirement alone.
    """
    gherkin_business = state.get("gherkin_business") or ""
    selected_env = state.get("selected_environment")
    normalised = state.get("normalised_requirement", "")

    if gherkin_business and selected_env:
        env_lines = (
            f"  Runtime    : {selected_env['runtime']}\n"
            f"  Framework  : {selected_env['framework']}\n"
            f"  Deployment : {selected_env['deployment']}\n"
            f"  Rationale  : {selected_env['rationale']}"
        )
        return (
            f"## Selected Environment\n{env_lines}\n\n"
            f"## Business Gherkin (immutable)\n{gherkin_business}\n\n"
            f"## Normalised Requirement (for traceability)\n{normalised}"
        )
    return normalised


def spec_advisor_node(state: NormaState) -> NormaState:
    user_message = _build_user_message(state)
    normalised = state.get("normalised_requirement", "")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = langfuse.get_prompt(
        _LANGFUSE_PROMPT_NAME, cache_ttl_seconds=_PROMPT_CACHE_TTL
    ).prompt

    with langfuse.start_as_current_observation(
        name="spec_advisor",
        as_type="span",
        input={
            "normalised_requirement": normalised,
            "has_gherkin_business": bool(state.get("gherkin_business")),
            "has_selected_environment": bool(state.get("selected_environment")),
            "model": MODEL,
        },
    ) as span:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.1,
                    "metadata": {
                        "generation_name": "spec-advisor-llm-call",
                        "tags": ["spec_advisor", "norma"],
                        "trace_id": langfuse.get_current_trace_id(),
                        "parent_observation_id": langfuse.get_current_observation_id(),
                    },
                },
            )

        resp.raise_for_status()
        raw_content = resp.json()["choices"][0]["message"]["content"].strip()
        advice = _parse_advice(raw_content)

        span.update(output={
            "specialist_count": len(advice),
            "languages": [r["language"] for r in advice],
            "raw": raw_content,
        })

    langfuse.flush()

    return {"spec_advice": advice}
