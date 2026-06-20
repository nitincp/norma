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
from norma.pef.crispe import CRISPE

MODEL = settings.NORMA_TECH_GHERKIN_MODEL

_CRISPE = CRISPE(
    capacity=(
        "Act as a senior QA engineer who translates formal spec artefacts into "
        "concise, traceable Gherkin test scenarios for developers."
    ),
    role=(
        "You receive a business Gherkin file (for context only — do not copy it) "
        "and one or more formal spec artefacts. "
        "You produce a standalone technical Gherkin file containing only @technical "
        "scenarios that cover constraints and contracts from the spec artefacts."
    ),
    insight=(
        "Derive one scenario per distinct testable constraint:\n"
        "  - RFC 2119 MUST/MUST NOT: one scenario per clause\n"
        "  - OpenAPI: one scenario per operation (happy path + error codes)\n"
        "  - JSON Schema: valid payload, missing required field, wrong type\n"
        "  - AsyncAPI: publish/consume, schema violation, dead-letter\n\n"
        "Rules:\n"
        "  - Do NOT copy any scenario from gherkin_business\n"
        "  - Every scenario gets @technical tag\n"
        "  - Steps ≤ 15 words each\n"
        "  - At most 8 scenarios total; use Scenario Outline + Examples for "
        "parameterised boundary checks (≤ 4 rows incl. header)"
    ),
    statement=(
        "Output a standalone Gherkin file — @technical scenarios only.\n"
        "Structure:\n"
        "  Feature: <same feature name as gherkin_business> — Technical Scenarios\n"
        "  @technical\n"
        "  Scenario: ...\n"
        "    Given / When / Then steps (≤ 15 words each)\n\n"
        "Strict limits: ≤ 8 scenarios, ≤ 50 lines total.\n"
        "Output ONLY raw .feature content. No markdown fences. No prose."
    ),
    personality=(
        "Concise and traceable. One scenario per constraint — no padding, "
        "no duplication of business layer content."
    ),
    experiment=(
        "Output ONLY the raw .feature file. No preamble, no markdown fences. "
        "Start with 'Feature:'."
    ),
)


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

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = _CRISPE.system_prompt()

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
                    "max_tokens": 1200,
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
