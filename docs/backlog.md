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

## REQ-004 — Two-Stage Pipeline: Business Sign-off + Technical Spec Generation

**Status:** Planned
**Added:** 2026-06-20

**Goal:** Restructure the single pipeline into two separate pipelines with a human-in-the-loop boundary between them, mirroring real-world delivery: SME signs off on behaviour and environment before any technical spec work begins.

**Motivation:** The Spec Advisor reading a semantic requirement blob has to make three inferences simultaneously (environment, contracts, constraints). With validated Gherkin + an explicit environment choice as inputs, those inferences collapse to one. Confidence and determinism improve significantly.

**Architecture:**

```
Pipeline 1 — Business Layer
  INTAKE
    ├──→ GHERKIN SPECIALIST  (business-readable behaviour)
    └──→ ENVIRONMENT ADVISOR (ranked environment options)
            ▼
      STAGE 1 GATE  (Gherkin coverage + env plausibility)
      [human-in-loop: SME picks environment, triggers Pipeline 2]

Pipeline 2 — Technical Layer
  [inputs: gherkin_business + selected_environment]
    ├──→ SPEC ADVISOR
    │       └── Send() fan-out → SPECIALIST(s) × N
    │                └── fan-in
    └──→ TECHNICAL GHERKIN SPECIALIST
         (enriches business Gherkin with technical scenarios from spec artefacts)
            ▼
      STAGE 2 GATE  (spec correctness + gherkin_technical covers all spec constraints)
```

**Key design decisions:**
- **Two separate LangGraph compilations** — Pipeline 2 is invoked with Pipeline 1 outputs + SME's environment selection as its initial state.
- **`gherkin_business` is immutable after Stage 1 Gate** — SME signs off on this; it never changes in Pipeline 2.
- **`gherkin_technical`** — generated by Technical Gherkin Specialist from `gherkin_business` + all spec artefacts; what the development team implements and tests against.
- **ENVIRONMENT ADVISOR** — new node; outputs ranked `environment_options[]`; SME (or automated test harness) picks one.
- **SPEC ADVISOR inputs change** — now reads `gherkin_business` + `selected_environment`, not raw/normalised requirement. Strong structured signal replaces semantic inference.
- **Stage 1 Gate** — validates Gherkin business coverage + environment plausibility (non-LLM + lightweight LLM rubric).
- **Stage 2 Gate** — validates spec correctness + that `gherkin_technical` covers all constraints expressed in spec artefacts.
- **Human-in-loop simulation** — automated test harness picks first environment option and invokes Pipeline 2; real deployment would pause for SME input.

**State boundary between pipelines:**
```python
# Pipeline 2 initial state (carried from Pipeline 1 output + SME selection)
{
    "gherkin_business": "...",       # immutable in P2
    "selected_environment": {...},   # SME's pick from environment_options
    "raw_requirement": "...",        # traceability
    "normalised_requirement": "...", # Spec Advisor may still want it
}
```

**Node inventory:**
| Node | Pipeline | Status |
|---|---|---|
| INTAKE | P1 | ✅ exists |
| GHERKIN SPECIALIST | P1 | ✅ exists (output key → `gherkin_business`) |
| ENVIRONMENT ADVISOR | P1 | ❌ new |
| STAGE 1 GATE | P1 | ❌ new (replaces current CAI Gate for business layer) |
| SPEC ADVISOR | P2 | ✅ exists (update inputs: Gherkin + env) |
| SPEC SPECIALIST (shell) | P2 | ✅ exists |
| TECHNICAL GHERKIN SPECIALIST | P2 | ❌ new |
| STAGE 2 GATE | P2 | ❌ new (replaces current CAI Gate for technical layer) |

---

### Tasks

#### T1 — Environment Advisor node ✓
- [x] CRISPE prompt: reads `normalised_requirement`; emits ranked `environment_options[]` — each with runtime, framework, deployment target, and rationale
- [x] `src/norma/graph/environment_advisor.py`
- [x] Add `environment_options: NotRequired[list[EnvironmentOption]]` + `selected_environment: NotRequired[EnvironmentOption]` to `NormaState`
- [x] Model: `cloud/claude-sonnet` (`NORMA_ENV_ADVISOR_MODEL` env var)
- [x] Langfuse span: `environment_advisor`

#### T2 — Stage 1 Gate + Pipeline 1 wiring ✓
- [x] Stage 1 Gate: Assertion 1 environment plausibility (non-LLM: at least one option present); Assertion 2 Gherkin business coverage (LLM rubric)
- [x] `src/norma/graph/stage1_gate.py`
- [x] Wire Pipeline 1: `intake → [gherkin_specialist ‖ environment_advisor] → stage1_gate`
- [x] `scripts/run_pipeline1.py` smoke test — prints status, env options, artefact paths
- [x] Output: `output/YYYY-MM-DD/HHMMSS/req_001.feature` + `req_001.environments.json` + `run_summary.json`

#### T3 — Spec Advisor update (Pipeline 2 inputs) ✓
- [x] Update CRISPE prompt: reads `gherkin_business` + `selected_environment` as primary signal
- [x] Tightened per-field length limits (rationale 1 sentence, insight 3 bullets) to prevent JSON truncation at 1500 tokens
- [x] Falls back to `normalised_requirement` alone for legacy pipeline

#### T4 — Technical Gherkin Specialist ✓
- [x] CRISPE prompt: reads `gherkin_business` + all `spec_artefacts`; emits standalone `@technical`-only Gherkin (no copying of business scenarios)
- [x] Runs after all SPEC SPECIALISTs complete (automatic fan-in via LangGraph)
- [x] `src/norma/graph/technical_gherkin_specialist.py`
- [x] Add `gherkin_technical: NotRequired[str]` to `NormaState`
- [x] Langfuse span: `technical_gherkin_specialist`

#### T5 — Stage 2 Gate + Pipeline 2 wiring ✓
- [x] Stage 2 Gate: Assertion 1 structural (Gherkin + RFC 2119 if present); Assertion 2 LLM rubric — standalone @technical file covers spec constraints
- [x] `src/norma/graph/stage2_gate.py`
- [x] Wire Pipeline 2: `spec_advisor → Send(spec_specialist) → technical_gherkin_specialist → stage2_gate`
- [x] `scripts/run_pipeline2.py` smoke test — auto-discovers latest P1 run folder

#### T7 — Observability: cost tracking + trace linking ✓
- [x] Root-caused Langfuse $0 cost: model alias names don't match Langfuse pricing catalog
- [x] Registered custom model price definitions in Langfuse via `/api/public/models` for all three `cloud/*` aliases
- [x] Added `trace_id` + `parent_observation_id` to LiteLLM `metadata` in all 9 node files so LiteLLM OTel spans nest under Norma spans
- [x] Added `model_info.base_model` to each entry in `docker/litellm-config.yaml`
- [x] Removed dead `local/qwen2.5-0.5b` entry and its fallback rule from `litellm-config.yaml`
- [x] Langfuse MCP credentials configured in `~/.claude/settings.json` (native HTTP Basic Auth)

#### T6 — End-to-end two-stage run ✓
- [x] `scripts/run_full.py` — runs Pipeline 1, auto-selects rank-1 environment, invokes Pipeline 2
- [x] Artefacts written to `output/YYYY-MM-DD/HHMMSS/` with `run_summary.json`
- [x] First clean run: PASS/PASS — 61.4s — specialists: rfc2119 + c4 + adr

---

**REQ-004 Status: DONE** — Closed 2026-06-20.
Two-stage pipeline runs end-to-end. Business layer (P1) and technical layer (P2) both gate on first attempt. Notes:
- Stage 1 Gate rubric required tightening: LLM produced verbose checklist instead of PASS/FAIL; fixed with explicit "no reasoning, no markdown" instruction and max_tokens 256→512.
- Spec Advisor JSON truncation bug found and fixed during first run (see findings.md).
- Business Gherkin tightened: ≤6 scenarios, steps ≤15 words, max_tokens 2048→800.
- Technical Gherkin is a standalone `@technical`-only file; business Gherkin is immutable after Stage 1 Gate.
- All scripts output to dated folders (`output/YYYY-MM-DD/HHMMSS/`) with `run_summary.json`.
- Cost per full run: ~$0.127 (cloud/claude-sonnet, 4 specialists: rfc2119 + openapi + jsonschema + c4; see findings.md for per-node breakdown).

---

## REQ-003 — Spec Advisor + Dynamic Specialist Pipeline

**Status:** Done
**Added:** 2026-06-20
**Closed:** 2026-06-20

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
