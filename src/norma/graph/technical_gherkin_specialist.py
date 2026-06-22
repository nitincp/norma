"""
Technical Gherkin Specialist node — produces a standalone technical scenario file.

Reads gherkin_business + all spec_artefacts; emits gherkin_technical: a
standalone Gherkin file containing ONLY @technical scenarios derived from the
spec artefacts. It does NOT copy or repeat business scenarios.

Relationship to gherkin_business:
  - gherkin_business  = SME-signed behaviour layer (human-readable, immutable)
  - gherkin_technical = dev/QA implementation layer (constraint + contract coverage)
  Both files are delivered together but remain independent documents.

Model: NORMA_TECH_GHERKIN_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: technical_gherkin_specialist
"""

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState

MODEL = settings.NORMA_TECH_GHERKIN_MODEL

_LANGFUSE_PROMPT_NAME = "norma.technical_gherkin_specialist"
_PROMPT_CACHE_TTL = 300  # seconds


def _build_user_message(state: NormaState) -> str:
    gherkin_business = state.get("gherkin_business", "")
    spec_artefacts = state.get("spec_artefacts") or {}

    artefact_sections = "\n\n".join(
        f"### {key.upper()} ARTEFACT\n{content}"
        for key, content in spec_artefacts.items()
    )

    return (
        f"## Business Gherkin (context only — do NOT copy these scenarios)\n"
        f"{gherkin_business}\n\n"
        f"## Spec Artefacts (derive @technical scenarios from these)\n"
        f"{artefact_sections if artefact_sections else '(none)'}"
    )


def technical_gherkin_specialist_node(state: NormaState) -> NormaState:
    user_message = _build_user_message(state)
    session_id = state.get("session_id")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = langfuse.get_prompt(
        _LANGFUSE_PROMPT_NAME, cache_ttl_seconds=_PROMPT_CACHE_TTL
    ).prompt

    with langfuse.propagate_attributes(session_id=session_id):
        with langfuse.start_as_current_observation(
            name="technical_gherkin_specialist",
            as_type="span",
            input={
                "artefact_keys": list((state.get("spec_artefacts") or {}).keys()),
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
                        "max_tokens": 2000,
                        "temperature": 0.1,
                        "metadata": {
                            "generation_name": "technical-gherkin-llm-call",
                            "tags": ["technical_gherkin_specialist", "norma"],
                            "trace_id": langfuse.get_current_trace_id(),
                            "parent_observation_id": langfuse.get_current_observation_id(),
                        },
                    },
                )

            resp.raise_for_status()
            gherkin_technical = resp.json()["choices"][0]["message"]["content"].strip()

            if gherkin_technical.startswith("```"):
                lines = gherkin_technical.splitlines()
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                gherkin_technical = "\n".join(lines).strip()

            span.update(output={"gherkin_technical_length": len(gherkin_technical)})

    langfuse.flush()

    return {"gherkin_technical": gherkin_technical}
