# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# First-time setup (creates .venv, installs deps, checks connectivity)
./scripts/bootstrap.sh

# Install (editable + dev deps)
pip install -e '.[dev]'

# Lint
ruff check src/
ruff format src/

# Type check
mypy src/

# Run tests
pytest
pytest tests/path/to/test_file.py::test_name   # single test

# Run the intake node smoke test
python scripts/run_intake.py

# Connectivity checks
python scripts/test_langfuse.py
python scripts/test_litellm.py

# Infra (Docker services on the Linux VM host) — or use /infra skill
./.claude/commands/infra/up.sh
./.claude/commands/infra/down.sh
./.claude/commands/infra/status.sh
./.claude/commands/infra/logs.sh
./.claude/commands/infra/restart.sh
```

## Architecture

Norma is a **LangGraph pipeline** that converts natural language requirements into layered spec bundles (OpenAPI, AsyncAPI, JSON Schema, Gherkin, MADR, C4 DSL).

### Service topology

All LLM traffic is routed through the **LiteLLM gateway**; Norma never calls model providers directly.

| Service | URL |
|---|---|
| Langfuse | `http://localhost:3000` |
| LiteLLM | `http://localhost:4000` |
| Ollama | `http://localhost:11434` |

Langfuse and LiteLLM run as Docker services on the **Linux VM host**. Ollama also runs directly on the Linux VM host.

### Model aliases (configured in `docker/litellm-config.yaml`)

| Alias | Backend |
|---|---|
| `local/qwen2.5-0.5b` | `ollama/qwen2.5:0.5b` |
| `local/phi3-mini` | `ollama/phi3:mini` |
| `cloud/claude-sonnet` | `anthropic/claude-sonnet-4-6` |
| `cloud/gpt-4o` | `gpt-4o` |
| `cloud/gemini-flash` | `gemini/gemini-2.5-flash-lite` |
| `cloud/grok` | `xai/grok-3-mini` |

### Graph pipeline

```
raw_requirement → INTAKE NODE (COSTAR) → SPEC ADVISOR (CRISPE) → SPEC SPECIALIST(s) [parallel]
  → CONSTITUTIONAL AI GATE (Promptfoo) → COMPOSER → spec bundle
```

**LangGraph state** is `NormaState` (TypedDict in `src/norma/graph/state.py`). Each node receives the full state dict and returns an updated copy.

### Prompt engineering (PEF)

Every LLM prompt is assembled from named PEF components in `src/norma/pef/`:
- `COSTAR` — Context · Objective · Style · Tone · Audience · Response (used for intake/classification)
- `CRISPE` — (planned) for spec-generation nodes
- CAI gate — constitutional AI validation

`COSTAR.system_prompt()` renders the full structured system prompt string. PEF classes are frozen dataclasses.

### Key invariants

- **No ad-hoc prompts** — all prompts come from PEF compositions
- **LiteLLM is the only inference endpoint** — `settings.LITELLM_BASE_URL` + `settings.LITELLM_MASTER_KEY`
- **Every node emits a Langfuse span** — use `langfuse.start_as_current_observation(..., as_type="span")`
- **CAI gate is not optional** — every artefact passes the gate before emission
- `OLLAMA_NUM_PARALLEL=1` is mandatory (CPU-only host, prevents thrashing)

### Configuration

`src/norma/settings.py` loads `.env` via `python-dotenv` and exposes typed constants. Required env vars raise `RuntimeError` if missing.

## Iteration model

Run → observe Langfuse traces → validate artefact → refine one PEF field → re-run. Don't rewrite whole prompts — surgical single-field edits only. See `docs/execution-model.md` for the full rhythm.

Model promotion: if a local model produces consistently poor output on a node, promote that node's model to `cloud/claude-sonnet` via the `NORMA_*_MODEL` env vars. Demote when the local model proves sufficient.
