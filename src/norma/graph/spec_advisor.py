"""
Spec Advisor node — CRISPE-prompted per-requirement bundle planner.

Reads normalised_requirement; emits spec_advice: a list of SpecRecommendation
dicts, each carrying a full CRISPE brief (role, insight, statement) that the
spec_specialist shell will execute directly. The LLM decides which industry-
standard spec languages are needed and writes the brief for each.

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
        "beyond the normalised requirement. "
        "Your output determines which specialists run and exactly what they produce."
    ),
    insight=(
        "Consider the full catalogue of industry-standard spec languages:\n"
        "  RFC 2119 / RFC 8174  — MUST/SHOULD/MAY conformance constraints\n"
        "  OpenAPI 3.1          — REST/HTTP API contracts\n"
        "  JSON Schema Draft 2020-12 — payload / data shape validation\n"
        "  AsyncAPI 3.0         — event, message, and queue contracts\n"
        "  C4 / Structurizr DSL — multi-system architecture diagrams\n"
        "  ADR (MADR format)    — architecture decision records\n\n"
        "Selection rules:\n"
        "  - Include a language only when the requirement explicitly states or "
        "clearly implies it is needed.\n"
        "  - Gherkin is always produced separately; never include it.\n"
        "  - When JSON Schema is needed, OpenAPI must also be included "
        "(depends_on: ['openapi']).\n"
        "  - Prefer a shorter list. If uncertain, omit.\n\n"
        "Brief quality rules:\n"
        "  - The 'role' field must fully describe what kind of author the specialist "
        "is acting as, referencing the specific standard.\n"
        "  - The 'insight' field must include requirement-specific context: which "
        "constraints, endpoints, payloads, or systems the specialist must address. "
        "Do not write generic insight — derive it from the requirement text.\n"
        "  - The 'statement' field must specify the exact output format, section "
        "headings, and any structural rules the artefact must follow."
    ),
    statement=(
        "Return a JSON array. Each element is an object with exactly these keys:\n\n"
        '  "language"              : human label (e.g. "RFC 2119", "OpenAPI 3.1")\n'
        '  "artefact_key"          : lowercase slug, no spaces (e.g. "rfc2119", "openapi")\n'
        '  "rationale"             : one sentence — why this spec is needed\n'
        '  "depends_on"            : array of artefact_key strings this must follow '
        "(empty array if none)\n"
        '  "requirement_segments"  : verbatim sentence(s) copied from the normalised '
        "requirement that this specialist is solely responsible for. "
        "Copy exact wording — do not paraphrase. Include only the sentences relevant "
        "to this standard; omit sentences that belong to other specialists.\n"
        '  "role"                  : CRISPE Role — what specialist author this LLM acts as\n'
        '  "insight"               : CRISPE Insight — analysis of the requirement_segments: '
        "what constraints, endpoints, or structures are present, and what rules to apply\n"
        '  "statement"             : CRISPE Statement — exact output format, required '
        "sections, and structural constraints\n\n"
        "Example element:\n"
        "{\n"
        '  "language": "RFC 2119",\n'
        '  "artefact_key": "rfc2119",\n'
        '  "rationale": "Requirement states a 2-second SLA and graceful API failure handling.",\n'
        '  "depends_on": [],\n'
        '  "requirement_segments": "The app must respond within 2 seconds. When ZenQuotes or '
        'JokeAPI are unavailable the app must display a friendly fallback message.",\n'
        '  "role": "You are a standards author writing RFC 2119 / RFC 8174 conformance clauses '
        'for a software system.",\n'
        '  "insight": "Two hard constraints are present: a 2-second latency ceiling and a '
        "mandatory user-facing fallback when external APIs fail. Both are MUST. "
        'No auth or async behaviour is mentioned.",\n'
        '  "statement": "Produce a document starting with \'# Constraints\'. Group MUST / SHOULD '
        "/ MAY / MUST NOT / SHOULD NOT statements under ## themed sub-sections. "
        "One bullet per statement. Mark inferred constraints with [implied]. "
        'Omit empty sections. Output must fit in 500 words."\n'
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


def spec_advisor_node(state: NormaState) -> NormaState:
    normalised = state["normalised_requirement"]

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = _CRISPE.system_prompt()

    with langfuse.start_as_current_observation(
        name="spec_advisor",
        as_type="span",
        input={"normalised_requirement": normalised, "model": MODEL},
    ) as span:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": normalised},
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.1,
                    "metadata": {
                        "generation_name": "spec-advisor-llm-call",
                        "tags": ["spec_advisor", "norma"],
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
