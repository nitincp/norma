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
        "Feature files that a test automation framework can execute directly."
    ),
    insight=(
        "The requirement describes a conversational app that greets the user based on time "
        "of day and lets them choose between a Quote of the Day or a Joke of the Day. "
        "Key paths: correct greeting, two content choices, graceful error handling."
    ),
    statement=(
        "Generate a complete Gherkin Feature file for the given normalised requirement. "
        "Include: Feature header, Background (if needed), and Scenario or Scenario Outline "
        "blocks covering the happy paths and at least one error path. "
        "Use concrete Examples tables for parameterised scenarios."
    ),
    personality="Precise, thorough, and idiomatic — no prose, only valid Gherkin syntax.",
    experiment=(
        "Output ONLY the raw .feature file content. "
        "Do not wrap it in markdown fences or add any explanation. "
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
                    "max_tokens": 2048,
                    "temperature": 0.2,
                    "metadata": {
                        "generation_name": "gherkin-specialist-llm-call",
                        "tags": ["gherkin", "norma"],
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
