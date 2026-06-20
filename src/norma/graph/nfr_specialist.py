"""
NFR Specialist node — CRISPE-prompted non-functional requirements extraction.

Accepts normalised_requirement + gherkin_content, emits nfr_content (structured
NFR document covering tech stack, external APIs, timeouts/retries, auth model,
and error handling expectations).

Model: NORMA_NFR_MODEL env var (default: cloud/claude-sonnet)
Langfuse span: nfr_specialist
"""

import httpx
from langfuse import Langfuse

from norma import settings
from norma.graph.state import NormaState
from norma.pef.crispe import CRISPE

MODEL = settings.NORMA_NFR_MODEL

_CRISPE = CRISPE(
    capacity=(
        "Act as a senior software architect who strictly follows YAGNI and KISS."
    ),
    role=(
        "You extract the minimum necessary non-functional requirements (NFRs) from a normalised "
        "software requirement and its Gherkin feature file, so a downstream code assistant can "
        "implement without guessing — but without inventing scope that was never asked for."
    ),
    insight=(
        "The Gherkin already captures WHAT the system does. Your job is only to answer: "
        "what runtime, which external APIs, what timeout/retry behaviour, what auth model, "
        "and how errors are surfaced to the user. "
        "YAGNI rule: if the requirement does not mention or imply a capability, do NOT add it. "
        "If a section cannot be answered from the requirement or Gherkin, write exactly: "
        "'Not specified — assistant's choice.' Do not invent an answer to fill the gap. "
        "Keep each decision to one concise line."
    ),
    statement=(
        "Produce an NFR document with exactly the following five sections:\n\n"
        "## Tech Stack\n"
        "Language, runtime, and framework only. One line each.\n\n"
        "## External APIs\n"
        "Named third-party APIs that the Gherkin implies, their base URLs, and what to do "
        "if they are unavailable (one sentence).\n\n"
        "## Timeouts & Retries\n"
        "Per-call timeout value and max retry count. No back-off algorithm unless required.\n\n"
        "## Auth Model\n"
        "State only what the requirement implies. If nothing is implied, write 'None — publicly "
        "accessible, no login required [assumed]'.\n\n"
        "## Error Handling\n"
        "User-facing error message text and logging level. Nothing else."
    ),
    personality=(
        "Minimal and decisive — one line per decision, no sub-bullets unless essential, "
        "no invented scope."
    ),
    experiment=(
        "Output ONLY the NFR document starting with '## Tech Stack'. "
        "No title, no preamble, no markdown fences. "
        "Mark inferred decisions with [assumed] inline. "
        "Total output must fit in 400 words."
    ),
)


def nfr_specialist_node(state: NormaState) -> NormaState:
    normalised = state["normalised_requirement"]
    gherkin = state.get("gherkin_content", "")

    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    system_prompt = _CRISPE.system_prompt()
    user_message = (
        f"NORMALISED REQUIREMENT:\n{normalised}\n\n"
        f"GHERKIN FEATURE FILE:\n{gherkin}"
    )

    with langfuse.start_as_current_observation(
        name="nfr_specialist",
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
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 700,
                    "temperature": 0.1,
                    "metadata": {
                        "generation_name": "nfr-specialist-llm-call",
                        "tags": ["nfr", "norma"],
                    },
                },
            )

        resp.raise_for_status()
        nfr_content = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip accidental markdown fences
        if nfr_content.startswith("```"):
            lines = nfr_content.splitlines()
            lines = [line for line in lines if not line.strip().startswith("```")]
            nfr_content = "\n".join(lines).strip()

        span.update(output={"nfr_content": nfr_content})

    langfuse.flush()

    return {"nfr_content": nfr_content}
