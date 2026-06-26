"""
Spec Specialist shell node — generic CRISPE-driven artefact producer.

This single node is dispatched N times in parallel by the graph (via Send),
once per SpecRecommendation in spec_advice. Each invocation fetches the fixed
CRISPE fields (capacity, personality, experiment) from Langfuse and assembles
a full prompt by injecting the Spec Advisor-generated fields at runtime:

  capacity    — from Langfuse (norma.spec_specialist_shell)
  role        — from recommendation.role
  insight     — from recommendation.insight
  statement   — two-phase prefix (code) + recommendation.statement
  personality — from Langfuse (norma.spec_specialist_shell)
  experiment  — from Langfuse (norma.spec_specialist_shell)

Prompt source: prompts/spec_specialist_shell.yaml → seeded to Langfuse.
Edit the YAML and re-run scripts/seed_prompts.py to update the live prompt.

The artefact is stored in spec_artefacts[recommendation.artefact_key].

Model: NORMA_DEFAULT_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: spec_specialist.<artefact_key>
"""

import re

import httpx
from langfuse import Langfuse, propagate_attributes

from norma import settings
from norma.graph.state import NormaState, SpecRecommendation
from norma.pef.crispe import CRISPE

MODEL = settings.NORMA_DEFAULT_MODEL

_LANGFUSE_PROMPT_NAME = "norma.spec_specialist_shell"
_PROMPT_CACHE_TTL = 300  # seconds

# Prepended to the Spec Advisor-generated statement at runtime.
# Lives in code (not YAML) because {language} is a runtime value.
_STATEMENT_PREFIX = (
    "Work in two phases:\n"
    "Phase 1 — Write a 4–6 line canonical example of a well-formed {language} artefact "
    "(structure, headings, keyword style). Label it '## EXAMPLE'.\n"
    "Phase 2 — Using that example as your structural scaffold, write the full artefact "
    "for the requirement segments below. Label it '## ARTEFACT'.\n\n"
    "Format rules from the Spec Advisor:\n"
)


def _parse_crispe_section(text: str, section: str) -> str:
    """Extract a named section value from a rendered CRISPE prompt string."""
    parts = re.split(r"^([A-Z]+):\n", text, flags=re.MULTILINE)
    # parts: [pre, name, content, name, content, ...]
    for i in range(1, len(parts) - 1, 2):
        if parts[i] == section:
            return parts[i + 1].strip()
    return ""


def _build_crispe(
    rec: SpecRecommendation,
    capacity: str,
    personality: str,
    experiment: str,
) -> CRISPE:
    return CRISPE(
        capacity=capacity,
        role=rec["role"],
        insight=rec["insight"],
        statement=_STATEMENT_PREFIX.format(language=rec["language"]) + rec["statement"],
        personality=personality,
        experiment=experiment,
    )


def _is_correction_mode(state: NormaState, rec: SpecRecommendation) -> bool:
    """True when this invocation is a targeted correction after a gate failure."""
    return (
        bool(state.get("gate_feedback"))
        and (state.get("revision_count", 0) > 0)
        and rec["artefact_key"] == state.get("gate_loser_key", "")
    )


def _build_correction_messages(
    rec: SpecRecommendation,
    gate_feedback: str,
    previous_artefact: str,
    authoritative_excerpt: str,
) -> tuple[str, str]:
    """Build (system, user) messages for correction mode — lean, no CRISPE overhead."""
    system = (
        f"You are {rec['role']}. "
        f"Your previous {rec['language']} artefact has a cross-spec inconsistency. "
        f"Correct only the conflicting definition. Keep everything else unchanged."
    )
    user = (
        f"Gate feedback: {gate_feedback}\n\n"
        f"Conform to this authoritative definition:\n{authoritative_excerpt}\n\n"
        f"Your previous artefact:\n{previous_artefact}\n\n"
        f"Return the full corrected artefact."
    )
    return system, user


def spec_specialist_node(state: NormaState) -> NormaState:
    rec = state["current_recommendation"]
    session_id = state.get("session_id")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    correction_mode = _is_correction_mode(state, rec)

    if correction_mode:
        previous_artefact = (state.get("spec_artefacts") or {}).get(rec["artefact_key"], "")
        system_prompt, user_message = _build_correction_messages(
            rec,
            gate_feedback=state.get("gate_feedback", ""),
            previous_artefact=previous_artefact,
            authoritative_excerpt=state.get("gate_authoritative_excerpt", ""),
        )
    else:
        prompt_text = langfuse.get_prompt(
            _LANGFUSE_PROMPT_NAME, cache_ttl_seconds=_PROMPT_CACHE_TTL
        ).prompt

        capacity = _parse_crispe_section(prompt_text, "CAPACITY")
        personality = _parse_crispe_section(prompt_text, "PERSONALITY")
        experiment = _parse_crispe_section(prompt_text, "EXPERIMENT")

        system_prompt = _build_crispe(rec, capacity, personality, experiment).system_prompt()
        user_message = (
            f"REQUIREMENT SEGMENTS (your scope — do not address anything outside this):\n"
            f"{rec['requirement_segments']}\n\n"
            f"SPEC LANGUAGE: {rec['language']}\n"
            f"RATIONALE: {rec['rationale']}"
        )

    with propagate_attributes(session_id=session_id):
        with langfuse.start_as_current_observation(
            name=f"spec_specialist.{rec['artefact_key']}",
            as_type="span",
            input={
                "artefact_key": rec["artefact_key"],
                "language": rec["language"],
                "model": MODEL,
                "correction_mode": correction_mode,
            },
        ) as span:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
                    json={
                        "model": MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message},
                        ],
                        "max_tokens": 1200,
                        "temperature": 0.1,
                        "metadata": {
                            "generation_name": f"spec-specialist-{rec['artefact_key']}-llm-call",
                            "tags": ["spec_specialist", rec["artefact_key"], "norma"],
                            "trace_id": langfuse.get_current_trace_id(),
                            "parent_observation_id": langfuse.get_current_observation_id(),
                        },
                    },
                )

            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()

            # Extract the ## ARTEFACT section produced by the two-phase prompt.
            # Fall back to the full response if the model omits the label.
            if "## ARTEFACT" in raw:
                content = raw.split("## ARTEFACT", 1)[1].strip()
            else:
                content = raw

            # Strip accidental markdown fences
            if content.startswith("```"):
                lines = [
                    line for line in content.splitlines()
                    if not line.strip().startswith("```")
                ]
                content = "\n".join(lines).strip()

            span.update(output={"artefact_key": rec["artefact_key"], "length": len(content)})

    langfuse.flush()

    return {"spec_artefacts": {rec["artefact_key"]: content}}
