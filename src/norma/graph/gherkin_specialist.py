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
MODEL = settings.NORMA_GHERKIN_MODEL

_LANGFUSE_PROMPT_NAME = "norma.gherkin_specialist"
_PROMPT_CACHE_TTL = 300  # seconds


def gherkin_specialist_node(state: NormaState) -> NormaState:
    normalised = state["normalised_requirement"]

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = langfuse.get_prompt(
        _LANGFUSE_PROMPT_NAME, cache_ttl_seconds=_PROMPT_CACHE_TTL
    ).prompt

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
