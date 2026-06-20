"""
Run a single Norma graph node against a saved state snapshot.

Usage:
    uv run python scripts/run_node.py <node_name> <snapshot.json> [--save]

Options:
    --save      Write output snapshot next to the input file as
                <snapshot>.<node_name>.out.json

Available nodes:
    intake
    gherkin_specialist
    environment_advisor
    stage1_gate
    spec_advisor
    spec_specialist
    technical_gherkin_specialist
    stage2_gate

Example:
    uv run python scripts/run_node.py intake tests/fixtures/state_empty.json
    uv run python scripts/run_node.py spec_advisor tests/fixtures/state_post_stage1.json --save
"""

import argparse
import json
import sys
from pathlib import Path

from norma import settings  # noqa: F401 — triggers load_dotenv
from norma.graph.state import NormaState

NODE_REGISTRY: dict[str, str] = {
    "intake": "norma.graph.intake:intake_node",
    "gherkin_specialist": "norma.graph.gherkin_specialist:gherkin_specialist_node",
    "environment_advisor": "norma.graph.environment_advisor:environment_advisor_node",
    "stage1_gate": "norma.graph.stage1_gate:stage1_gate_node",
    "spec_advisor": "norma.graph.spec_advisor:spec_advisor_node",
    "spec_specialist": "norma.graph.spec_specialist:spec_specialist_node",
    "technical_gherkin_specialist": "norma.graph.technical_gherkin_specialist:technical_gherkin_specialist_node",
    "stage2_gate": "norma.graph.stage2_gate:stage2_gate_node",
}


def _load_node(dotted: str):
    module_path, fn_name = dotted.split(":")
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def _diff(before: dict, after: dict) -> dict:
    """Return keys that are new or changed in after vs before."""
    changed = {}
    for k, v in after.items():
        if k not in before or before[k] != v:
            changed[k] = v
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single Norma node against a state snapshot.")
    parser.add_argument("node", choices=list(NODE_REGISTRY), help="Node name to run")
    parser.add_argument("snapshot", help="Path to input state JSON file")
    parser.add_argument("--save", action="store_true", help="Save output snapshot alongside input")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        print(f"ERROR: snapshot not found: {snapshot_path}", file=sys.stderr)
        sys.exit(1)

    state: NormaState = json.loads(snapshot_path.read_text())
    node_fn = _load_node(NODE_REGISTRY[args.node])

    print(f"Node     : {args.node}")
    print(f"Snapshot : {snapshot_path}")
    print(f"Input keys: {list(state.keys())}")
    print()

    try:
        result = node_fn(state)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    changed = _diff(dict(state), dict(result))

    print("─" * 60)
    print(f"CHANGED / NEW KEYS ({len(changed)}):")
    for k, v in changed.items():
        if isinstance(v, str) and len(v) > 300:
            preview = v[:300].replace("\n", "↵") + "…"
            print(f"  {k}: {preview}")
        else:
            print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:300]}")
    print("─" * 60)

    merged = {**dict(state), **dict(result)}

    if args.save:
        out_path = snapshot_path.with_suffix(f".{args.node}.out.json")
        out_path.write_text(json.dumps(merged, indent=2))
        print(f"\nOutput snapshot saved: {out_path}")
    else:
        print("\nFull output state (JSON):")
        print(json.dumps(merged, indent=2))


if __name__ == "__main__":
    main()
