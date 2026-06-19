# Norma — Requirement Backlog

Requirements queued for processing through the Norma pipeline.
Each entry is raw natural language — Norma's intake node handles normalisation.

See [execution-model.md](execution-model.md) for how tasks are built and iterated.

---

## REQ-001 — Greeting + Daily Content App

**Status:** In progress  
**Added:** 2026-06-16

**Raw requirement:**

> Generate application to greet user with proper time like Good Morning, Evening. And ask if he/she want to see Quote of the Day or Joke of the Day. And Reply.

**Pipeline decision (YAGNI/KISS):** 3-node minimal pipeline. One output artefact: Gherkin.
Expand to JSON Schema, MADR, C4 only after this loop closes cleanly.

```
Requirement → INTAKE (COSTAR) → GHERKIN SPECIALIST (CRISPE) → CAI GATE → .feature artefact
```

---

### Tasks

#### T1 — INTAKE NODE ✓
- [x] Write COSTAR prompt composition for requirement normalisation (`src/norma/pef/costar.py`)
- [x] Implement LangGraph node: accepts raw string, emits normalised requirement + actor/dep list (`src/norma/graph/intake.py`)
- [x] Model: promoted to `cloud/claude-sonnet` — `local/qwen2.5-0.5b` too small for format following; `local/phi3-mini` timed out on CPU-only
- [x] Langfuse span: `intake`
- **Done:** node runs and emits a clean normalised paragraph + bullet list of actors and external deps.
- **Observation:** Format-following requires a capable model; small local models fail at structured output without fine-tuning. Intake stays cloud until a local model is benchmarked on this task.

#### T2 — GHERKIN SPECIALIST NODE ✓
- [x] Write CRISPE prompt composition for Gherkin generation (`src/norma/pef/crispe.py`)
- [x] Implement LangGraph node: accepts normalised requirement, emits `.feature` file content (`src/norma/graph/gherkin_specialist.py`)
- [x] Model: promoted to `cloud/claude-sonnet` — `local/phi3-mini` timed out on CPU-only (same as T1); `NORMA_GHERKIN_MODEL` env var (default: `cloud/claude-sonnet`)
- [x] Langfuse span: `gherkin_specialist`
- [x] Smoke test: `python scripts/run_gherkin_specialist.py` — PASS, `.feature` starts with `Feature:`, 6–7 Scenario blocks
- **Done:** node emits a syntactically valid `.feature` file covering the interaction flow.

**Actions before T4:** ✓ both applied
- [x] Set `NORMA_GHERKIN_MODEL=cloud/claude-sonnet` default in `settings.py`; remove local models from LiteLLM config and `.env.example`
- [x] Raise `max_tokens` to 2048 in `gherkin_specialist_node`
- See [findings.md](findings.md) for full trace analysis.

#### T3 — CAI GATE NODE ✓
- [x] Assertion 1: parse validity (non-LLM regex: `Feature:` + `Scenario` + `Given/When/Then`)
- [x] Assertion 2: LLM rubric — "covers time-of-day greeting, both content choices, one error path"
- [x] Revision loop: fail → back to T2 with gate feedback appended; max 2 revisions (`route_after_gate`)
- [x] Model: `cloud/claude-sonnet` (`NORMA_CAI_GATE_MODEL` env var)
- [x] Langfuse span: `cai_gate`
- [x] Smoke test: `python scripts/run_cai_gate.py` — PASS; `FORCE_FAIL=1` → structural fail + router says `revise`
- **Done:** gate passes both assertions on valid Gherkin; rejects broken input and routes correctly.

#### T4 — WIRE + FIRST RUN ✓
- [x] Connect T1 → T2 → T3 as LangGraph state graph
- [x] Run with REQ-001 raw requirement as input
- [x] End-to-end smoke test: `python scripts/run_pipeline.py` — PASS
- **Done:** full pipeline runs end-to-end and produces a validated `.feature` file.

---

**REQ-001 Status: DONE** — Closed 2026-06-19.
Pipeline closed on first gate attempt. Boring in the right way. Notes:
- All three nodes required `cloud/claude-sonnet`; local models (phi3-mini, qwen2.5-0.5b) too small or too slow (CPU-only timeout).
- CAI gate passed first attempt — the CRISPE Gherkin output was structurally sound.
- Cost per run ~$0.016–$0.020 with all-cloud config.
- Span tree unified properly once the full graph ran under a single Langfuse trace (T4 confirmed this).

---

## REQ-002 — NFR Specialist Node

**Status:** Queued
**Added:** 2026-06-19

**Signal:** REQ-001 build evaluation (Claude Code vs Gemini) revealed that the Gherkin spec alone is insufficient context for an assistant to build correctly without guessing. Claude Code succeeded by making its own assumptions (tech stack, API endpoints, timeout values, retry limits). Gemini failed entirely. The missing layer is non-functional requirements.

**Goal:** Add an NFR Specialist node to the pipeline that extracts or infers non-functional requirements from the raw requirement and appends them to the spec bundle alongside the Gherkin artefact.

**NFR categories to cover:**
- Tech stack / runtime constraints
- External API choices and fallbacks
- Timeout and retry limits
- Auth model
- Error handling expectations

**Pipeline position:**
```
INTAKE → GHERKIN SPECIALIST → NFR SPECIALIST → CAI GATE → spec bundle (Gherkin + NFR doc)
```

**Done when:** A spec bundle containing both a `.feature` file and an NFR doc can be handed to any code assistant and produce a correct, consistent implementation without guessing.

---

## INFRA-001 — Retire Devcontainer

**Status:** Done
**Added:** 2026-06-16
**Closed:** 2026-06-17

**Goal:** Open the project directly from the Linux VM folder. No devcontainer required to develop or run Norma.

**Context:**
- All Docker services (Langfuse, LiteLLM) already run on the Linux VM host, not inside the devcontainer.
- Ollama runs directly on the Linux VM host at `localhost:11434`.
- From bare Linux, all services are reachable via `localhost` — no devcontainer networking needed.

**Tasks:**

- [x] Fix CLAUDE.md: correct Ollama description (runs on Linux VM host, not Windows/Hyper-V)
- [x] Audit `.devcontainer/` for env vars or mounts not captured in `.env`; migrate anything missing
- [x] Write `scripts/bootstrap.sh`: create venv, `pip install -e '.[dev]'`, verify connectivity
- [x] Pin Python version: `requires-python = ">=3.12"` already set in `pyproject.toml`
- [x] Update `.env` and `.env.example`: all URLs now use `localhost`
- [x] Delete `.devcontainer/`
- [x] Update CLAUDE.md: added bootstrap command, removed devcontainer reference
- [ ] Smoke test: `python scripts/run_intake.py` passes from bare Linux venv

**Done when:** A developer can clone the repo, run `scripts/bootstrap.sh`, and execute `python scripts/run_intake.py` with no devcontainer involved.
