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
from langfuse import Langfuse, propagate_attributes

from norma import settings
from norma.graph.state import EnvironmentOption, NormaState

MODEL = settings.NORMA_ENV_ADVISOR_MODEL

_LANGFUSE_PROMPT_NAME = "norma.environment_advisor"
_PROMPT_CACHE_TTL = 300  # seconds


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
    session_id = state.get("session_id")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = langfuse.get_prompt(
        _LANGFUSE_PROMPT_NAME, cache_ttl_seconds=_PROMPT_CACHE_TTL
    ).prompt

    with propagate_attributes(session_id=session_id):
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
