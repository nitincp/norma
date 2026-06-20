"""
Gherkin Specialist node — CRISPE-prompted Gherkin generation.

Accepts normalised_requirement, emits gherkin_content (.feature file text).

Model: NORMA_GHERKIN_MODEL env var (default: local/phi3-mini)
Langfuse span: gherkin_specialist
"""

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState
from norma.pef.crispe import CRISPE

MODEL = settings.NORMA_GHERKIN_MODEL

_CRISPE = CRISPE(
    capacity=(
        "Act as a senior QA engineer with deep expertise in Behaviour-Driven Development "
        "and the Gherkin specification language."
    ),
    role=(
        "You convert normalised software requirements into syntactically valid Gherkin "
        "Feature files that a business stakeholder can read and sign off on. "
        "No technical implementation detail — behaviour only."
    ),
    insight=(
        "Focus on the minimum set of scenarios that covers the requirement completely:\n"
        "  - One Scenario Outline per parameterised behaviour (e.g. time-band → greeting)\n"
        "  - One Scenario per distinct happy path\n"
        "  - One Scenario per error/failure path\n"
        "Do not duplicate coverage. Background is only needed when ≥3 scenarios share "
        "the same Given steps."
    ),
    statement=(
        "Generate a Gherkin Feature file for the given requirement.\n"
        "Strict limits:\n"
        "  - At most 6 scenarios or scenario outlines total\n"
        "  - Each step (Given/When/Then/And) ≤ 15 words\n"
        "  - Examples tables: ≤ 4 rows including header\n"
        "  - No nested rules blocks\n"
        "  - No comments or tags\n"
        "  - Total file length: under 80 lines\n"
        "Coverage requirement: every distinct behaviour in the requirement MUST appear "
        "as at least one scenario step. Do not merge unrelated behaviours into one step."
    ),
    personality="Economical and precise — every line must earn its place. No padding.",
    experiment=(
        "Output ONLY the raw .feature file content. "
        "Do not wrap in markdown fences or add explanation. "
        "Start with the 'Feature:' keyword on the first line."
    ),
)


def gherkin_specialist_node(state: NormaState) -> NormaState:
    normalised = state["normalised_requirement"]

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = _CRISPE.system_prompt()

    with langfuse.start_as_current_observation(
        name="gherkin_specialist",
        as_type="span",
        input={"normalised_requirement": normalised, "model": MODEL},
    ) as span:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": normalised},
                    ],
                    "max_tokens": 1200,
                    "temperature": 0.2,
                    "metadata": {
                        "generation_name": "gherkin-specialist-llm-call",
                        "tags": ["gherkin", "norma"],
                        "trace_id": langfuse.get_current_trace_id(),
                        "parent_observation_id": langfuse.get_current_observation_id(),
                    },
                },
            )

        resp.raise_for_status()
        gherkin_content = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip accidental markdown fences if the model ignores the instruction
        if gherkin_content.startswith("```"):
            lines = gherkin_content.splitlines()
            lines = [line for line in lines if not line.strip().startswith("```")]
            gherkin_content = "\n".join(lines).strip()

        span.update(output={"gherkin_content": gherkin_content})

    langfuse.flush()

    return {"gherkin_content": gherkin_content}
