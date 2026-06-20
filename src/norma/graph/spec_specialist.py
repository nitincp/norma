"""
Spec Specialist shell node — generic CRISPE-driven artefact producer.

This single node is dispatched N times in parallel by the graph (via Send),
once per SpecRecommendation in spec_advice. Each invocation reads
state["current_recommendation"] and assembles a full CRISPE prompt from it:

  capacity   — fixed: specialist author framing
  role       — from recommendation.role       (Spec Advisor-generated)
  insight    — from recommendation.insight    (Spec Advisor-generated, requirement-specific)
  statement  — from recommendation.statement  (Spec Advisor-generated, format rules)
  personality — fixed: standards-conformant precision
  experiment  — fixed: output discipline

The artefact is stored in spec_artefacts[recommendation.artefact_key].

Model: NORMA_DEFAULT_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: spec_specialist.<artefact_key>
"""

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState, SpecRecommendation
from norma.pef.crispe import CRISPE

MODEL = settings.NORMA_DEFAULT_MODEL

# Fixed CRISPE fields — stable across all specialist invocations.
# Role, insight, and statement are injected per-invocation from the recommendation.
_CAPACITY = (
    "Act as a senior specification author with deep expertise in the formal standard "
    "you have been briefed to apply. Produce artefacts that a code assistant can "
    "implement from directly, without clarifying questions."
)

_PERSONALITY = (
    "Standards-conformant and precise. Use the exact terminology of the target standard. "
    "No invented scope — every statement must be traceable to the requirement text or "
    "marked [implied]. No filler, no preamble."
)

_EXPERIMENT = (
    "Output ONLY the artefact as specified in STATEMENT. "
    "No title beyond what STATEMENT prescribes. No preamble. No markdown fences. "
    "Mark inferred content with [implied] inline."
)


def _build_crispe(rec: SpecRecommendation) -> CRISPE:
    return CRISPE(
        capacity=_CAPACITY,
        role=rec["role"],
        insight=rec["insight"],
        statement=rec["statement"],
        personality=_PERSONALITY,
        experiment=_EXPERIMENT,
    )


def spec_specialist_node(state: NormaState) -> NormaState:
    rec = state["current_recommendation"]

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = _build_crispe(rec).system_prompt()
    user_message = (
        f"REQUIREMENT SEGMENTS (your scope — do not address anything outside this):\n"
        f"{rec['requirement_segments']}\n\n"
        f"SPEC LANGUAGE: {rec['language']}\n"
        f"RATIONALE: {rec['rationale']}"
    )

    with langfuse.start_as_current_observation(
        name=f"spec_specialist.{rec['artefact_key']}",
        as_type="span",
        input={
            "artefact_key": rec["artefact_key"],
            "language": rec["language"],
            "model": MODEL,
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
                    },
                },
            )

        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip accidental markdown fences
        if content.startswith("```"):
            lines = [l for l in content.splitlines() if not l.strip().startswith("```")]
            content = "\n".join(lines).strip()

        span.update(output={"artefact_key": rec["artefact_key"], "length": len(content)})

    langfuse.flush()

    return {"spec_artefacts": {rec["artefact_key"]: content}}
