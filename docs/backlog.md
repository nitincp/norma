# Norma — Requirement Backlog

Requirements queued for processing through the Norma pipeline.
Each entry is raw natural language — Norma's intake node handles normalisation.

See [PROCESS.md](PROCESS.md) for how tasks are built and iterated.

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
- [x] Model: `cloud/claude-sonnet` (`NORMA_INTAKE_MODEL` env var)
- [x] Langfuse span: `intake`
- **Done:** node runs and emits a clean normalised paragraph + bullet list of actors and external deps.

#### T2 — GHERKIN SPECIALIST NODE ✓
- [x] Write CRISPE prompt composition for Gherkin generation (`src/norma/pef/crispe.py`)
- [x] Implement LangGraph node: accepts normalised requirement, emits `.feature` file content (`src/norma/graph/gherkin_specialist.py`)
- [x] Model: `cloud/claude-sonnet` (`NORMA_GHERKIN_MODEL` env var)
- [x] Langfuse span: `gherkin_specialist`
- [x] Smoke test: `python scripts/run_gherkin_specialist.py` — PASS, `.feature` starts with `Feature:`, 6–7 Scenario blocks
- [x] Raise `max_tokens` to 2048
- **Done:** node emits a syntactically valid `.feature` file covering the interaction flow.

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
- CAI gate passed first attempt — the CRISPE Gherkin output was structurally sound.
- Cost per run ~$0.016–$0.020.
- Span tree unified properly once the full graph ran under a single Langfuse trace (T4 confirmed this).

---

## REQ-002 — Constraints Specialist Node (shipped as NFR)

**Status:** Done
**Added:** 2026-06-19
**Closed:** 2026-06-19

**Signal:** REQ-001 build evaluation revealed that Gherkin alone is insufficient — a code assistant must guess tech stack, API choices, timeouts, and auth model. The missing layer is a constraints artefact.

**Note:** Shipped as an "NFR doc" (non-standard). REQ-003 replaces this node with an **RFC 2119 Constraints Specialist** that emits MUST/SHOULD/MAY statements — a proper standard. The NFR node is a stepping stone.

**Categories covered:**
- Tech stack / runtime constraints
- External API choices and fallbacks
- Timeout and retry limits
- Auth model
- Error handling expectations

**Pipeline position:**
```
INTAKE → GHERKIN SPECIALIST → NFR SPECIALIST → CAI GATE → spec bundle (Gherkin + NFR doc)
```

---

### Tasks

#### T1 — NFR SPECIALIST NODE ✓
- [x] Add `nfr_content: NotRequired[str]` to `NormaState`
- [x] Add `NORMA_NFR_MODEL` env var to `settings.py` (default: `cloud/claude-sonnet`)
- [x] Create `src/norma/graph/nfr_specialist.py` — CRISPE-prompted, reads `normalised_requirement` + `gherkin_content`, emits structured NFR doc with five mandatory sections
- [x] Wire into graph: `gherkin_specialist → nfr_specialist → cai_gate`
- [x] Add Assertion 2 (NFR structural check) to CAI gate — non-LLM, verifies all 5 headings present
- [x] Rename old Assertion 2 → Assertion 3 in CAI gate
- [x] Unit tests: `tests/test_nfr_specialist.py` — 5 tests, all pass

#### T2 — SMOKE TEST ✓
- [x] Add `scripts/run_nfr_specialist.py` standalone smoke test — PASS
- [x] End-to-end pipeline run with REQ-001 input; verify both `gherkin_content` and `nfr_content` in final state — PASS, gate on first attempt
- [x] Validate NFR doc covers all 5 categories for the greeting app domain — all 5 sections present
- [x] Artefacts written to `output/req_001.nfr.md` alongside `output/req_001.feature`

---

## REQ-003 — Spec Advisor + Dynamic Specialist Pipeline

**Status:** Planned
**Added:** 2026-06-20

**Goal:** Restructure the pipeline so that bundle composition is determined per-requirement, not hardcoded. The Spec Advisor reads INTAKE output and recommends which spec languages are needed. Only the recommended specialists run.

**Architecture decisions:**
- **INTAKE fans out in parallel** to GHERKIN SPECIALIST and SPEC ADVISOR — both start immediately from the normalised requirement.
- **GHERKIN SPECIALIST is permanent** — every requirement has behaviour; `.feature` is always in the bundle.
- **SPEC ADVISOR is permanent** — reads INTAKE; outputs a structured recommendation: which spec languages, why, and sequencing constraints (e.g. JSON Schema needs OpenAPI first). Uses CRISPE.
- **SPEC SPECIALIST(s) are dynamic** — injected by the graph based on Spec Advisor output; each reads INTAKE directly. Not every requirement needs every specialist.
- **NFR node (REQ-002) retired** — the Spec Advisor will recommend RFC 2119 when constraints are needed; an RFC 2119 Specialist is one of the injectable candidates.
- **CAI GATE validates whatever artefacts are present** — assertions are keyed to the artefact type, not a fixed bundle shape.

**Candidate spec specialists (injectable):**
| Specialist | Standard | Artefact |
|---|---|---|
| RFC 2119 Constraints | RFC 2119 / RFC 8174 | `req.constraints.md` |
| HTTP Contract | OpenAPI 3.1 | `req.openapi.yaml` |
| Payload Shapes | JSON Schema Draft 2020-12 | `req.schema.json` |
| Architecture | C4 / Structurizr DSL | `req.c4` |
| Async Events | AsyncAPI 3.0 | `req.asyncapi.yaml` |

**Pipeline shape:**
```
                          ┌─ GHERKIN SPECIALIST ──────────────────────────────┐
INTAKE ───────────────────┤                                                    ├─ CAI GATE → spec bundle
                          └─ SPEC ADVISOR → SPEC SPECIALIST(s) [per advice] ──┘
```

**Build loop validation:**
- Run Norma on REQ-001 → spec bundle in `output/specs/req_001/`
- Point a code assistant at that folder with the prompt: _"Implement the application described in this spec bundle."_ The bundle carries everything; the prompt carries nothing.
- Any guess or clarifying question is a Norma failure → identify gap → fix responsible PEF composition.

---

### Tasks

#### T1 — Spec Advisor node
- [ ] CRISPE prompt: reads `normalised_requirement`; emits structured advice — list of recommended spec languages with rationale and any ordering constraints
- [ ] `src/norma/graph/spec_advisor.py`
- [ ] Add `spec_advice: NotRequired[list[SpecRecommendation]]` to `NormaState` (SpecRecommendation: `{language: str, rationale: str, depends_on: list[str]}`)
- [ ] Model: `cloud/claude-sonnet` (`NORMA_SPEC_ADVISOR_MODEL` env var)
- [ ] Langfuse span: `spec_advisor`
- [ ] Smoke test: `scripts/run_spec_advisor.py` — verify advice for REQ-001 recommends RFC 2119 at minimum

#### T2 — Dynamic specialist routing
- [ ] Graph router reads `spec_advice` and injects the appropriate specialist nodes
- [ ] Specialists with no `depends_on` run in parallel; sequenced specialists wait for their dependency
- [ ] Each specialist reads `normalised_requirement` from state (INTAKE output) directly
- [ ] Merge node collects all specialist outputs before CAI GATE

#### T3 — RFC 2119 Constraints Specialist
- [ ] `src/norma/graph/rfc2119_specialist.py` (replaces `nfr_specialist.py`)
- [ ] CRISPE prompt: reads `normalised_requirement`; emits MUST/SHOULD/MAY statements grouped by category
- [ ] `constraints_content: NotRequired[str]` in `NormaState` (rename from `nfr_content`)
- [ ] CAI gate assertion: MUST/SHOULD/MAY keywords present; mandatory categories covered
- [ ] Model: `cloud/claude-sonnet` (`NORMA_CONSTRAINTS_MODEL` env var)
- [ ] Smoke test: `scripts/run_rfc2119_specialist.py`

#### T4 — Parallel INTAKE fan-out
- [ ] Refactor graph entry: INTAKE → parallel [GHERKIN SPECIALIST, SPEC ADVISOR]
- [ ] SPEC ADVISOR output gates specialist injection (T2)
- [ ] End-to-end smoke test: GHERKIN and at least one dynamic specialist present in final state

#### T5 — Build loop test (REQ-001)
- [ ] Run Norma on REQ-001; write bundle to `output/specs/req_001/`
- [ ] Claude Code session: `implement the application described in this spec bundle` (no other context)
- [ ] Record: any guesses, any clarifying questions, any spec gaps
- [ ] Triage gaps → PEF refinement tasks

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
