"""
Intake node — COSTAR-prompted requirement normalisation.

Accepts raw_requirement string, emits:
  normalised_requirement  — precise single paragraph
  actors                  — list of human/system actors
  external_deps           — list of external services/APIs/data sources

Model: NORMA_DEFAULT_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: intake
"""

import re

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState
from norma.pef.costar import COSTAR

MODEL = (
    settings.NORMA_DEFAULT_MODEL
)  # default: local/qwen2.5-0.5b; override via NORMA_DEFAULT_MODEL

_COSTAR = COSTAR(
    context=(
        "You are an analyst in a software specification pipeline. "
        "You receive raw informal requirement text and normalise it into a precise description."
    ),
    objective=(
        "Rewrite the requirement as one clear paragraph with no ambiguity. "
        "List every actor (human role or system component that acts). "
        "List every external dependency (API, service, or data source the system needs)."
    ),
    style="Technical and precise. Active voice. No vague terms like 'etc' or 'and so on'.",
    tone="Analytical and neutral.",
    audience=(
        "Engineers who will generate Gherkin, OpenAPI, and C4 specifications from this output."
    ),
    response_format=(
        "Reply using this three-section structure:\n"
        "NORMALISED: <paragraph>\n"
        "ACTORS: <bullet list>\n"
        "EXTERNAL_DEPS: <bullet list or 'none'>"
    ),
)


def _parse_output(text: str) -> tuple[str, list[str], list[str]]:
    """
    Extract three sections from the LLM response.

    Handles both block format (header on its own line) and inline format
    (header and content on the same line), and strips markdown bold markers.
    """
    # Strip bold markdown so "**Actor**" becomes "Actor"
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    known = ("NORMALISED", "ACTORS", "EXTERNAL_DEPS")

    for line in text.splitlines():
        matched = False
        for key in known:
            prefix = f"{key}:"
            if line.upper().startswith(prefix):
                if current_key:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = key
                inline = line[len(prefix) :].strip()
                current_lines = [inline] if inline else []
                matched = True
                break
        if not matched and current_key is not None:
            # Stop accumulating at an unrecognised heading-like line (e.g. "RESPONSE FORMAT:")
            if re.match(r"^[A-Z][A-Z _]+:$", line.strip()):
                sections[current_key] = "\n".join(current_lines).strip()
                current_key = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    normalised = sections.get("NORMALISED", "").strip() or text.strip()

    def _bullets(block: str) -> list[str]:
        items = []
        for line in block.splitlines():
            # Strip list markers, then strip the "Actor — description" to just the name
            line = line.strip().lstrip("-•*").strip()
            # Take only the part before " — " if present (actor name vs description)
            line = line.split(" — ")[0].strip()
            if line and line.lower() not in ("none", ""):
                items.append(line)
        return items

    return (
        normalised,
        _bullets(sections.get("ACTORS", "")),
        _bullets(sections.get("EXTERNAL_DEPS", "")),
    )


def intake_node(state: NormaState) -> NormaState:
    raw = state["raw_requirement"]

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = _COSTAR.system_prompt()

    with langfuse.start_as_current_observation(
        name="intake",
        as_type="span",
        input={"raw_requirement": raw, "model": MODEL},
    ) as span:
        with httpx.Client(timeout=40.0) as client:
            resp = client.post(
                f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": raw},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.1,
                    "metadata": {
                        "generation_name": "intake-llm-call",
                        "tags": ["intake", "norma"],
                    },
                },
            )

        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        normalised, actors, deps = _parse_output(content)

        span.update(
            output={
                "normalised_requirement": normalised,
                "actors": actors,
                "external_deps": deps,
            }
        )

    langfuse.flush()

    return {
        **state,
        "normalised_requirement": normalised,
        "actors": actors,
        "external_deps": deps,
    }
