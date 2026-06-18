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

**Langfuse + LiteLLM trace analysis (2026-06-19):**
- **Model actually used: `cloud/claude-sonnet`** — `local/phi3-mini` silently fell back. LiteLLM's 30s `request_timeout` for phi3-mini triggered, then the configured fallback `{ local/phi3-mini: [cloud/claude-sonnet] }` kicked in. Same failure mode as T1. Model should be promoted to `cloud/claude-sonnet` via `NORMA_GHERKIN_MODEL=cloud/claude-sonnet` in `.env`.
- **Output truncated at 1024 tokens** — the final scenario was cut mid-sentence (last line of raw output: `And the user selects "`). `max_tokens=1024` is too tight for a 6–7 scenario feature file. Raise to 2048 in the node.
- **Wall time ~79s** breakdown: ~30s waiting for phi3-mini to timeout + ~16s Claude Sonnet inference (Langfuse `latency: 15.958s`) + ~33s httpx/Langfuse flush overhead.
- **Token counts:** 340 prompt tokens, 1024 completion tokens (capped), 1364 total. Cost: $0.01638/run.
- **Non-determinism:** scenario count varied 6 vs 7 between two runs at `temperature=0.2`. Expected for a generative task; CAI gate (T3) will catch structural gaps.
- **Trace naming:** LiteLLM's OTel integration creates a root trace named `gherkin-specialist-llm-call` separate from the Norma `gherkin_specialist` span — same pattern as intake. Span tree will only unify properly in T4 when the full graph runs under a single Langfuse trace.

**Actions before T4:** ✓ both applied
- [x] Set `NORMA_GHERKIN_MODEL=cloud/claude-sonnet` default in `settings.py`; remove `local/phi3-mini` from LiteLLM config and `.env.example`
- [x] Raise `max_tokens` to 2048 in `gherkin_specialist_node`

#### T3 — CAI GATE NODE
- [ ] Assertion 1: parse validity (`gherkin-lint` — not LLM)
- [ ] Assertion 2: LLM rubric — "covers time-of-day greeting, both content choices, one error path"
- [ ] Revision loop: fail → back to T2 with gate feedback appended; max 2 revisions
- [ ] Model: `cloud/claude-sonnet` (rubric judge only)
- [ ] Langfuse span: `cai_gate`
- **Done when:** gate passes both assertions.

#### T4 — WIRE + FIRST RUN
- [ ] Connect T1 → T2 → T3 as LangGraph state graph
- [ ] Run with REQ-001 raw requirement as input
- [ ] Open Langfuse traces: check span tree, token counts, latency per node
- [ ] Record: did gate pass on attempt 1 or 2? What did it catch?
- **Done when:** full pipeline runs end-to-end and produces a validated `.feature` file.

---

**Stop condition:** If T4 closes on first or second gate attempt — REQ-001 is done.
Note what was boring, note what was interesting, move to next requirement.

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
