# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# First-time setup (installs uv-managed Python 3.12, syncs deps, checks connectivity)
./scripts/bootstrap.sh

# Sync dependencies (after pulling or editing pyproject.toml)
uv sync --extra dev

# Lint
uv run ruff check src/
uv run ruff format src/

# Type check
uv run mypy src/

# Run tests
uv run pytest
uv run pytest tests/path/to/test_file.py::test_name   # single test

# Run the intake node smoke test
uv run python scripts/run_intake.py

# Connectivity checks
uv run python scripts/test_langfuse.py
uv run python scripts/test_litellm.py

# Infra (Docker services on the Linux VM host) — or use /infra skill
./.claude/commands/infra/up.sh
./.claude/commands/infra/down.sh
./.claude/commands/infra/status.sh
./.claude/commands/infra/logs.sh
./.claude/commands/infra/restart.sh
```

## Architecture

Norma is a **LangGraph pipeline** that converts natural language requirements into layered spec bundles. The bundle composition is determined per-requirement by the Spec Advisor.

### Service topology

All LLM traffic is routed through the **LiteLLM gateway**; Norma never calls model providers directly.

| Service | URL |
|---|---|
| Langfuse | `http://localhost:3000` |
| LiteLLM | `http://localhost:4000` |

Langfuse and LiteLLM run as Docker services on the **Linux VM host**.

### Model aliases (configured in `docker/litellm-config.yaml`)

| Alias | Backend |
|---|---|
| `cloud/claude-sonnet` | `anthropic/claude-sonnet-4-6` |
| `cloud/gpt-4o` | `gpt-4o` |
| `cloud/gemini-flash` | `gemini/gemini-2.5-flash-lite` |
| `cloud/grok` | `xai/grok-3-mini` |

### Graph pipeline

```
                          ┌─ GHERKIN SPECIALIST ──────────────────────────────┐
INTAKE ───────────────────┤                                                    ├─ CAI GATE → spec bundle
                          └─ SPEC ADVISOR → SPEC SPECIALIST(s) [per advice] ──┘
```

- **INTAKE** — normalises the raw requirement (COSTAR); permanent
- **GHERKIN SPECIALIST** — always runs in parallel with Spec Advisor; reads INTAKE; emits `.feature` file
- **SPEC ADVISOR** — reads INTAKE; recommends which spec languages and layers are needed for this requirement (CRISPE); permanent
- **SPEC SPECIALIST(s)** — injected dynamically based on Spec Advisor output; each reads INTAKE; candidates: RFC 2119, OpenAPI, JSON Schema, C4 DSL, AsyncAPI, …
- **CAI GATE** — validates all artefacts; permanent

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

### Configuration

`src/norma/settings.py` loads `.env` via `python-dotenv` and exposes typed constants. Required env vars raise `RuntimeError` if missing.

## Iteration model

Run → observe Langfuse traces → validate artefact → refine one PEF field → re-run. Don't rewrite whole prompts — surgical single-field edits only. See `docs/PROCESS.md` for the full rhythm.

All nodes default to `cloud/claude-sonnet`. Cost reduction is via cheaper cloud aliases (`cloud/grok`, `cloud/gemini-flash`) once quality is baselined on a node.
