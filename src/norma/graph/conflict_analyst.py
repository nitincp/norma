"""
Conflict Analyst node — runs on Stage 2 Gate failure only.

Reads gate_feedback + all spec_artefacts + spec_advice (for depends_on relationships)
and produces:
  gate_winner_key          — artefact_key of the authoritative spec (higher layer)
  gate_loser_key           — artefact_key of the spec that must be corrected
  gate_authoritative_excerpt — minimal conflicting definition from the winner

Layer hierarchy is determined by depends_on: the artefact that others depend on wins.
The LLM identifies the conflicting keys and extracts the authoritative excerpt;
winner/loser resolution from depends_on is done in code for reliability.

Model: NORMA_CONFLICT_ANALYST_MODEL (default: cloud/gemini-flash — lightweight task)
Langfuse span: conflict_analyst
"""

import json
import re

import httpx
from langfuse import Langfuse, propagate_attributes

from norma import settings
from norma.graph.state import NormaState, SpecRecommendation

MODEL = settings.NORMA_CONFLICT_ANALYST_MODEL

_LANGFUSE_PROMPT_NAME = "norma.conflict_analyst"
_PROMPT_CACHE_TTL = 300


def _resolve_winner_loser(
    conflicting_keys: list[str],
    advice: list[SpecRecommendation],
) -> tuple[str, str] | None:
    """
    Given two conflicting artefact keys, determine winner and loser via depends_on.
    Returns (winner_key, loser_key) or None if hierarchy cannot be resolved.
    """
    if len(conflicting_keys) < 2:
        return None
    key_a, key_b = conflicting_keys[0], conflicting_keys[1]
    rec_map = {r["artefact_key"]: r for r in advice}

    rec_a = rec_map.get(key_a)
    rec_b = rec_map.get(key_b)
    if not rec_a or not rec_b:
        return None

    a_depends_on_b = key_b in rec_a.get("depends_on", [])
    b_depends_on_a = key_a in rec_b.get("depends_on", [])

    if a_depends_on_b:
        return key_b, key_a   # b wins, a must correct
    if b_depends_on_a:
        return key_a, key_b   # a wins, b must correct
    return None  # same layer — cannot resolve


def conflict_analyst_node(state: NormaState) -> NormaState:
    gate_feedback = state.get("gate_feedback", "")
    spec_artefacts = state.get("spec_artefacts") or {}
    advice = state.get("spec_advice") or []
    session_id = state.get("session_id")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = langfuse.get_prompt(
        _LANGFUSE_PROMPT_NAME, cache_ttl_seconds=_PROMPT_CACHE_TTL
    ).prompt

    # Build user message: gate feedback + artefact contents + dependency map
    dep_lines = "\n".join(
        f"  {r['artefact_key']} depends_on: {r['depends_on'] or '[]'}"
        for r in advice
    )
    artefact_block = "\n\n".join(
        f"### {key}\n{content}" for key, content in spec_artefacts.items()
    )
    user_message = (
        f"## Gate Feedback\n{gate_feedback}\n\n"
        f"## Dependency Map\n{dep_lines}\n\n"
        f"## Spec Artefacts\n{artefact_block}"
    )

    with propagate_attributes(session_id=session_id):
        with langfuse.start_as_current_observation(
            name="conflict_analyst",
            as_type="span",
            input={"gate_feedback": gate_feedback, "artefact_keys": list(spec_artefacts.keys())},
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
                        "max_tokens": 400,
                        "temperature": 0.0,
                        "metadata": {
                            "generation_name": "conflict-analyst-llm-call",
                            "tags": ["conflict_analyst", "norma"],
                            "trace_id": langfuse.get_current_trace_id(),
                            "parent_observation_id": langfuse.get_current_observation_id(),
                        },
                    },
                )

            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()

            # Parse JSON response
            text = re.sub(r"```[a-z]*\n?", "", raw).strip().rstrip("`").strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                span.update(output={"error": "failed to parse LLM response", "raw": raw})
                langfuse.flush()
                return {}

            llm_conflicting = [str(k) for k in parsed.get("conflicting_keys", [])]
            llm_excerpt = str(parsed.get("authoritative_excerpt", "")).strip()

            # Resolve winner/loser in code via depends_on (more reliable than LLM)
            resolved = _resolve_winner_loser(llm_conflicting, advice)
            if resolved:
                winner_key, loser_key = resolved
            else:
                # Fall back to LLM's determination if code can't resolve
                winner_key = str(parsed.get("winner_key", ""))
                loser_key = str(parsed.get("loser_key", ""))

            span.update(output={
                "conflicting_keys": llm_conflicting,
                "winner_key": winner_key,
                "loser_key": loser_key,
                "authoritative_excerpt_length": len(llm_excerpt),
            })

    langfuse.flush()

    return {
        "gate_winner_key": winner_key,
        "gate_loser_key": loser_key,
        "gate_authoritative_excerpt": llm_excerpt,
    }
