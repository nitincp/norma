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

Model: NORMA_SPEC_ADVISOR_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: spec_advisor
"""

import json
import re

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState, SpecRecommendation
from norma.pef.crispe import CRISPE

MODEL = settings.NORMA_SPEC_ADVISOR_MODEL

_CRISPE = CRISPE(
    capacity=(
        "Act as a principal software architect who selects the minimum necessary "
        "formal specification languages for a software requirement and writes a "
        "precise execution brief for each one."
    ),
    role=(
        "You plan a specification bundle for a downstream pipeline. "
        "For each spec language you recommend, you produce a self-contained brief "
        "that a generic specialist LLM can execute without any additional context "
        "beyond what you supply. "
        "Your output determines which specialists run and exactly what they produce."
    ),
    insight=(
        "You receive two structured inputs:\n"
        "  1. BUSINESS GHERKIN — SME-validated behaviour scenarios (immutable).\n"
        "  2. SELECTED ENVIRONMENT — the chosen runtime, framework, and deployment "
        "target chosen by the SME.\n\n"
        "These replace the raw requirement as your primary signal. "
        "Use them to eliminate guesswork: the environment makes technology-specific "
        "standards (OpenAPI, AsyncAPI) unambiguous; the Gherkin makes behavioural "
        "contracts explicit.\n\n"
        "Consider the full catalogue of industry-standard spec languages:\n"
        "  RFC 2119 / RFC 8174  — MUST/SHOULD/MAY conformance constraints\n"
        "  OpenAPI 3.1          — REST/HTTP API contracts\n"
        "  JSON Schema Draft 2020-12 — payload / data shape validation\n"
        "  AsyncAPI 3.0         — event, message, and queue contracts\n"
        "  C4 / Structurizr DSL — multi-system architecture diagrams\n"
        "  ADR (MADR format)    — architecture decision records\n\n"
        "Selection rules:\n"
        "  - Include a language only when Gherkin steps or the selected environment "
        "explicitly imply it is needed.\n"
        "  - Gherkin is always produced separately; never include it.\n"
        "  - When JSON Schema is needed, OpenAPI must also be included "
        "(depends_on: ['openapi']).\n"
        "  - Prefer a shorter list. If uncertain, omit.\n\n"
        "Brief quality rules:\n"
        "  - The 'role' field must fully describe what kind of author the specialist "
        "is acting as, referencing the specific standard.\n"
        "  - The 'insight' field must include requirement-specific context derived "
        "from the Gherkin steps and selected environment: which constraints, "
        "endpoints, payloads, or systems the specialist must address.\n"
        "  - The 'statement' field must specify the exact output format, section "
        "headings, and any structural rules the artefact must follow."
    ),
    statement=(
        "Return a JSON array. Each element is an object with exactly these keys.\n"
        "FIELD LENGTH LIMITS — stay within these or the output will be truncated:\n"
        "  rationale            : 1 sentence max\n"
        "  requirement_segments : 2 sentences max — only the sentences directly "
        "relevant to this standard\n"
        "  role                 : 1 sentence max\n"
        "  insight              : 3 bullet points max, one line each\n"
        "  statement            : 4 lines max — artefact structure and section headings only\n\n"
        "Keys:\n"
        '  "language"              : human label (e.g. "RFC 2119", "OpenAPI 3.1")\n'
        '  "artefact_key"          : lowercase slug, no spaces (e.g. "rfc2119", "openapi")\n'
        '  "rationale"             : 1 sentence — why this spec is needed\n'
        '  "depends_on"            : array of artefact_key strings (empty array if none)\n'
        '  "requirement_segments"  : ≤2 verbatim sentences from the requirement; '
        "copy exact wording, omit sentences that belong to other specialists\n"
        '  "role"                  : CRISPE Role — 1 sentence, what specialist author\n'
        '  "insight"               : CRISPE Insight — ≤3 bullet lines: key '
        "constraints, endpoints, or structures to address\n"
        '  "statement"             : CRISPE Statement — ≤4 lines: artefact format, '
        "required section headings, structural constraints\n\n"
        "Example element:\n"
        "{\n"
        '  "language": "RFC 2119",\n'
        '  "artefact_key": "rfc2119",\n'
        '  "rationale": "Requirement states a 2s SLA and graceful API failure handling.",\n'
        '  "depends_on": [],\n'
        '  "requirement_segments": "The app must respond within 2 seconds. '
        'When APIs are unavailable show a friendly fallback.",\n'
        '  "role": "You are a standards author writing RFC 2119 conformance clauses.",\n'
        '  "insight": "- MUST: 2s latency ceiling\\n'
        '- MUST: user-facing fallback on API failure\\n'
        '- MUST NOT: crash or hang",\n'
        "  \"statement\": \"Start with '# Constraints'. Group under ## sub-sections. "
        'One bullet per clause. Mark inferred with [implied]."\n'
        "}"
    ),
    personality=(
        "Architecturally decisive and requirement-faithful. "
        "Every recommended spec must be justified by the requirement text. "
        "Every brief must be specific enough that a specialist LLM produces a correct "
        "artefact on the first attempt."
    ),
    experiment=(
        "Output ONLY the JSON array. No preamble, no explanation, no markdown fences. "
        "If no spec languages are needed beyond Gherkin, return an empty array: []"
    ),
)

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

    system_prompt = _CRISPE.system_prompt()

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
