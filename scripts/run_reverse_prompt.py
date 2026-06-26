"""
Reverse prompting — ask a failing model what system prompt would produce a target output.

Given:
  - the input the node received (from a state snapshot)
  - the desired output (from a Sonnet PASS run)

Asks the model: "What system prompt would make you produce this output?"
Prints the suggestion. User decides whether to apply it as a YAML edit.

Usage:
    uv run python scripts/run_reverse_prompt.py \\
        --node gherkin_specialist \\
        --model cloud/gemini-flash \\
        --snapshot tests/fixtures/state_post_intake.json \\
        --target output/2026-06-27/034015/req_001.feature

    uv run python scripts/run_reverse_prompt.py \\
        --node spec_advisor \\
        --model cloud/grok \\
        --snapshot tests/fixtures/state_post_stage1.json \\
        --target output/2026-06-27/034015/req_001.spec_advice.debug.json
"""

import argparse
import json
from pathlib import Path

import httpx

from norma import settings  # noqa: F401 — triggers load_dotenv

# Which state key to extract as the "input" for each node
_NODE_INPUT_KEY: dict[str, str] = {
    "gherkin_specialist": "normalised_requirement",
    "spec_advisor": "normalised_requirement",
    "technical_gherkin_specialist": "normalised_requirement",
    "environment_advisor": "normalised_requirement",
    "stage1_gate": "gherkin_feature",
    "stage2_gate": "spec_artefacts",
}


def _call(model: str, messages: list[dict]) -> str:
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{settings.LITELLM_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.LITELLM_MASTER_KEY}"},
            json={"model": model, "messages": messages, "temperature": 0.2},
        )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reverse-prompt a model for a specific node failure.")
    parser.add_argument("--node", required=True, choices=list(_NODE_INPUT_KEY), help="Failing node name")
    parser.add_argument("--model", required=True, help="Failing model alias, e.g. cloud/gemini-flash")
    parser.add_argument("--snapshot", required=True, help="Input state snapshot JSON (pre-node)")
    parser.add_argument("--target", required=True, help="Target output file (Sonnet PASS artefact)")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    target_path = Path(args.target)

    if not snapshot_path.exists():
        raise SystemExit(f"Snapshot not found: {snapshot_path}")
    if not target_path.exists():
        raise SystemExit(f"Target not found: {target_path}")

    state = json.loads(snapshot_path.read_text())
    target_output = target_path.read_text()

    input_key = _NODE_INPUT_KEY[args.node]
    node_input = state.get(input_key, "")
    if not node_input:
        raise SystemExit(f"Key '{input_key}' not found or empty in snapshot")

    prompt = f"""You are a prompt engineer. I am trying to get a language model (you) to produce a specific output for a node called "{args.node}" in a document generation pipeline.

Here is the INPUT the node receives:
---
{node_input}
---

Here is the DESIRED OUTPUT (produced by a reference model that passes all quality checks):
---
{target_output}
---

Your task: write a system prompt (or the key instructions within a system prompt) that would reliably make you produce output like the desired output above when given the same input.

Be specific about:
- The persona or role you should adopt
- Exact format constraints (structure, headings, field names, ordering)
- Any output discipline rules (what to include, what to omit)
- Any failure modes you can anticipate and how to avoid them

Output only the suggested system prompt text. No preamble, no explanation."""

    print(f"Node    : {args.node}")
    print(f"Model   : {args.model}")
    print(f"Snapshot: {snapshot_path}")
    print(f"Target  : {target_path}")
    print(f"Input key used: {input_key}")
    print("─" * 60)
    print("Calling model …\n")

    suggestion = _call(args.model, [{"role": "user", "content": prompt}])

    print("SUGGESTED SYSTEM PROMPT:")
    print("─" * 60)
    print(suggestion)
    print("─" * 60)
    print(f"\nNext: apply relevant parts as a surgical edit to prompts/{args.node}.yaml")


if __name__ == "__main__":
    main()
