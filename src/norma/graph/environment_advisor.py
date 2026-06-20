"""
Environment Advisor node — ranks candidate runtime environments for the requirement.

Reads normalised_requirement; emits environment_options: a ranked list of
EnvironmentOption dicts (runtime, framework, deployment target, rationale).

Model: NORMA_ENV_ADVISOR_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: environment_advisor
"""

import json
import re

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import EnvironmentOption, NormaState
from norma.pef.crispe import CRISPE

MODEL = settings.NORMA_ENV_ADVISOR_MODEL

_CRISPE = CRISPE(
    capacity=(
        "Act as a senior solutions architect who recommends the minimum viable "
        "set of runtime environments for a software requirement, ranked by fit."
    ),
    role=(
        "You produce a ranked list of candidate environments so that a human SME "
        "can select one before detailed technical spec work begins. "
        "Each option must be self-consistent (runtime + framework + deployment "
        "fit together) and justified by the requirement text."
    ),
    insight=(
        "Consider these axes when choosing environments:\n"
        "  - Runtime: language version + interpreter (e.g. Python 3.12, Node 22, JVM 21)\n"
        "  - Framework: primary web / CLI / event framework (e.g. FastAPI, Express, Spring Boot)\n"
        "  - Deployment: target platform (e.g. Docker/AWS Lambda, GCP Cloud Run, Kubernetes)\n\n"
        "Selection rules:\n"
        "  - Derive from the requirement; don't import generic best practices.\n"
        "  - Rank 1 is the most obvious fit; include up to 3 options.\n"
        "  - Omit options that are clearly incompatible with the requirement.\n"
        "  - Rationale must reference specific words or phrases from the requirement."
    ),
    statement=(
        "Return a JSON array. Each element has exactly these keys:\n\n"
        '  "runtime"    : language + version (e.g. "Python 3.12")\n'
        '  "framework"  : primary framework (e.g. "FastAPI")\n'
        '  "deployment" : deployment target (e.g. "Docker / AWS Lambda")\n'
        '  "rationale"  : one sentence citing the requirement\n'
        '  "rank"       : integer starting at 1 (1 = most recommended)\n\n'
        "Output ONLY the JSON array. No preamble, no markdown fences."
    ),
    personality=(
        "Pragmatic and requirement-faithful. "
        "Prefer widely adopted stacks unless the requirement implies otherwise."
    ),
    experiment=(
        "Output ONLY the JSON array. No preamble, no explanation, no markdown fences."
    ),
)


def _parse_options(text: str) -> list[EnvironmentOption]:
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

    options: list[EnvironmentOption] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        required = ("runtime", "framework", "deployment", "rationale", "rank")
        if not all(item.get(f) for f in required):
            continue
        options.append(
            EnvironmentOption(
                runtime=str(item["runtime"]),
                framework=str(item["framework"]),
                deployment=str(item["deployment"]),
                rationale=str(item["rationale"]),
                rank=int(item["rank"]),
            )
        )
    return sorted(options, key=lambda o: o["rank"])


def environment_advisor_node(state: NormaState) -> NormaState:
    normalised = state["normalised_requirement"]

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = _CRISPE.system_prompt()

    with langfuse.start_as_current_observation(
        name="environment_advisor",
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
                    "max_tokens": 800,
                    "temperature": 0.1,
                    "metadata": {
                        "generation_name": "environment-advisor-llm-call",
                        "tags": ["environment_advisor", "norma"],
                        "trace_id": langfuse.get_current_trace_id(),
                        "parent_observation_id": langfuse.get_current_observation_id(),
                    },
                },
            )

        resp.raise_for_status()
        raw_content = resp.json()["choices"][0]["message"]["content"].strip()
        options = _parse_options(raw_content)

        span.update(output={
            "option_count": len(options),
            "options": [f"[{o['rank']}] {o['runtime']} / {o['framework']}" for o in options],
            "raw": raw_content,
        })

    langfuse.flush()

    return {"environment_options": options}
