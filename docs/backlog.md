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

#### T2 — GHERKIN SPECIALIST NODE
- [ ] Write CRISPE prompt composition for Gherkin generation
- [ ] Implement LangGraph node: accepts normalised requirement, emits `.feature` file content
- [ ] Model: `local/phi3-mini`
- [ ] Langfuse span: `gherkin_specialist`
- **Done when:** node emits a syntactically valid `.feature` file covering the interaction flow.

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
