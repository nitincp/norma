"""
One-time Langfuse prompt seeding script.

Reads all prompts/*.yaml files and pushes them to Langfuse as new versions.
Run this after editing a YAML file to make the change live in the pipeline.

Each push creates a new version in Langfuse and labels it 'production'.
Prior versions are preserved — Langfuse keeps the full history.

Usage:
    uv run python scripts/seed_prompts.py               # seed all prompts
    uv run python scripts/seed_prompts.py spec_advisor  # seed one prompt by node name
"""

import sys
from pathlib import Path

import yaml
from langfuse import Langfuse

# triggers load_dotenv
from norma import settings  # noqa: F401

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def _render_costar(data: dict) -> str:
    """Assemble COSTAR fields into a single system prompt string."""
    return (
        f"CONTEXT:\n{data['context'].strip()}\n\n"
        f"OBJECTIVE:\n{data['objective'].strip()}\n\n"
        f"STYLE:\n{data['style'].strip()}\n\n"
        f"TONE:\n{data['tone'].strip()}\n\n"
        f"AUDIENCE:\n{data['audience'].strip()}\n\n"
        f"RESPONSE FORMAT:\n{data['response_format'].strip()}"
    )


def _render_crispe(data: dict) -> str:
    """Assemble CRISPE fields into a single system prompt string."""
    parts = []
    for field in ("capacity", "role", "insight", "statement", "personality", "experiment"):
        if field in data:
            parts.append(f"{field.upper()}:\n{data[field].strip()}")
    return "\n\n".join(parts)


def _render_rubric(data: dict) -> str:
    return data["rubric_system"].strip()


_RENDERERS = {
    "COSTAR": _render_costar,
    "CRISPE": _render_crispe,
    "rubric": _render_rubric,
}


def seed_prompt(lf: Langfuse, yaml_path: Path) -> None:
    data = yaml.safe_load(yaml_path.read_text())
    framework = data.get("framework", "").upper()
    langfuse_name = data["langfuse_name"]

    renderer = _RENDERERS.get(framework) or _RENDERERS.get(data.get("framework", ""))
    if not renderer:
        print(f"  SKIP {yaml_path.name} — unknown framework '{framework}'")
        return

    prompt_text = renderer(data)

    lf.create_prompt(
        name=langfuse_name,
        prompt=prompt_text,
        labels=["production"],
        type="text",
    )
    print(f"  SEEDED {langfuse_name}  ({yaml_path.name})")


def main() -> None:
    lf = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
    )

    filter_node = sys.argv[1] if len(sys.argv) > 1 else None
    yaml_files = sorted(PROMPTS_DIR.glob("*.yaml"))

    if filter_node:
        yaml_files = [f for f in yaml_files if filter_node in f.stem]
        if not yaml_files:
            print(f"No prompt file matching '{filter_node}' found in {PROMPTS_DIR}")
            sys.exit(1)

    print(f"Seeding {len(yaml_files)} prompt(s) to Langfuse at {settings.LANGFUSE_HOST}...\n")
    for path in yaml_files:
        seed_prompt(lf, path)

    lf.flush()
    print("\nDone.")


if __name__ == "__main__":
    main()
