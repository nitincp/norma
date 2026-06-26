# Norma — Run Findings

Observations from pipeline runs. Updated after each significant run or trace analysis session.
The format: what happened, what the numbers were, what it means going forward.

---

## 2026-06-27 — REQ-005 T6: A/B re-run after T1–T5 fixes

**Context:** `scripts/run_ab_test.py` — three sequential runs after all T1–T5 fixes (granular execution, self-anchoring one-shot, conflict correction loop). Same requirement (REQ-001). `NORMA_DEFAULT_MODEL` added to `_MODEL_KEYS` (was missing — spec specialists previously ran as sonnet regardless of variant).

**Results summary:**

| Variant | Model | P1 | P2 | Wall time | Cost | Specialists | Env selected | Revisions |
|---|---|---|---|---|---|---|---|---|
| sonnet | cloud/claude-sonnet | PASS | PASS | 93.9s | $0.1128 | rfc2119, openapi, jsonschema, c4, adr | Node.js 22 / Express | 0 |
| gemini | cloud/gemini-flash | FAIL | — | 11.3s | — | — | — | 0 |
| grok | cloud/grok | PASS | FAIL | 36.5s | $0.0028 | (none) | Python 3.12 / stdlib | 2 |

**Findings by variant:**

**Sonnet** — clean PASS/PASS, zero revisions. Conflict correction loop not triggered (T5 fix succeeded — no cross-specialist inconsistency this run). Ran all 5 specialists (rfc2119, openapi, jsonschema, c4, adr). Cost $0.1128, 93.9s total.

**Gemini** — P1 failure in 11.3s. Stage 1 Gate rejected Business Gherkin: `"The requirement to retrieve and display the chosen content is not explicitly captured as a named feature in the Gherkin."` The Business Gherkin Specialist missed a named feature. Run dir not written (P1 fail exits early). Different failure mode from the June 20 run (which was an RFC `# Constraints` heading gap); the `# Constraints` fix (T3 self-anchoring one-shot) appears to have resolved that quirk, but Gherkin feature coverage is now failing. Root cause: gemini-flash Business Gherkin Specialist is producing a feature file that omits one or more scenarios that the gate deems required. The gate prompt says "no boundary/edge-case testing required" but Gemini is dropping a named feature outright.

**Grok** — P1 passed but Spec Advisor returned `[]` again (empty JSON). No specialists ran. Technical Gherkin produced output with no `Scenario` blocks (same structural failure as June 20). Stage 2 Gate failed; revision loop ran 2 cycles but could not fix a structural defect introduced by the specialist. Cost $0.0028 (cheap but useless). The T4 one-shot JSON anchor in the Spec Advisor prompt did not hold for grok-3-mini — model still produces empty or unparseable output.

**T3–T5 impact assessment:**
- T3 (self-anchoring one-shot): resolved the gemini RFC `# Constraints` heading gap from June 20. Gemini now has a different failure. Net positive.
- T4 (Spec Advisor one-shot JSON anchor): did not fix grok JSON truncation. Grok Spec Advisor still returns `[]`. One-shot insufficient for this quirk.
- T5 (conflict correction loop): Sonnet now produces clean P2 PASS without hitting the cross-specialist inconsistency that plagued the June 20 run. The loop works — or Sonnet naturally avoided the conflict this time (non-deterministic). Revision_count=0 suggests no conflict was triggered, not that the loop fixed one.

**Next quirk fixes required:**
1. **Gemini Business Gherkin** — missing named feature. Fix: audit what scenario gemini omits, add it as a one-shot example or strengthen the coverage instruction in the Business Gherkin YAML. Use `run_node.py` targeting gemini on `gherkin_specialist`.
2. **Grok Spec Advisor** — `[]` JSON output persists. One-shot insufficient. Next: reverse prompting loop (see REQ-005 Problem 2 fix order) — feed grok a Sonnet PASS `spec_advice.json` and ask it to suggest a prompt that would produce the same. Cap at 3 cycles.
3. **Grok Technical Gherkin** — no Scenario blocks. Fix order same: one-shot already tried (T3); proceed to reverse prompting.

**Target from backlog:** all three models pass P1; Sonnet and Gemini pass P2. Currently only Sonnet achieves both. T6 is partially done — run complete, failures documented, fixes identified.

---

## 2026-06-22 — Langfuse prompt management wired; e2e runs (sonnet + grok)

**Context:** All five nodes (intake, gherkin_specialist, cai_gate, spec_advisor, spec_specialist) now fetch their prompts from Langfuse at runtime. `prompts/*.yaml` is the canonical source of truth. Seeded and ran end-to-end.

**Prompt management change:**
- Nodes no longer contain hardcoded PEF dataclass blocks. Each fetches via `langfuse.get_prompt(name, cache_ttl_seconds=300)`.
- `seed_prompts.py` is now part of the required workflow before any run after a YAML edit.
- Trace ↔ prompt version linkage is now live — every Langfuse trace shows which prompt version produced it.
- `gherkin_specialist.yaml` was stale (insight was requirement-specific instead of generic structural guidance); synced to current code before seeding.

**Sonnet run 1** — P1 PASS, P2 PASS, 0 specialists, `revision_count: 1`.
- Spec Advisor returned empty advice during pipeline execution despite returning 5 specialists when called in isolation with the same Gherkin + environment input. Intermittent — likely non-determinism at `temperature=0.1` combined with the verbose Gherkin+environment context.
- `revision_count: 1` indicates Stage 2 Gate failed once and the pipeline cycled before passing.

**Sonnet run 2** — P1 PASS, P2 FAIL, 3 specialists (rfc2119, openapi, jsonschema).
- Spec Advisor performed correctly. Stage 2 Gate caught real technical Gherkin coverage gaps:
  - Missing upper-boundary time tests (e.g. 11:59 for Good Morning)
  - Missing GET /quote 503 scenario
  - Missing GET /joke 200 scenario
  - Missing QuoteResponse `"quote"` field rejection test
- This is the gate working correctly — the technical Gherkin did not fully exercise the spec artefacts. No prompt fix needed; this is a coverage gap the next iteration should close.

**Grok run** — P1 FAIL. Stage 1 Gate caught incomplete business Gherkin: missing the content selection scenario (user prompted to choose Quote or Joke). Known Grok weakness — Gherkin generation quality insufficient for this requirement at current prompt settings.

**Outstanding issues:**
1. Grok P1 Gherkin incompleteness — needs targeted `gherkin_specialist.yaml` fix or model-specific prompt variant
2. Sonnet Spec Advisor intermittent empty advice — monitor; if recurring, tighten the one-shot example or add a non-empty assertion in `_parse_advice`
3. Sonnet Stage 2 Gate coverage failure — expected behaviour; technical Gherkin needs another refinement cycle

---

## 2026-06-20 — Langfuse cost tracking + observability fixes

**Context:** After the A/B test, Langfuse was showing $0 cost for all traces despite correct token usage counts. Also, LiteLLM-generated OTel spans were appearing as disconnected root traces rather than nested under their Norma node spans.

**Problem 1 — Zero cost in Langfuse:**
- Root cause: Langfuse's pricing catalog has no entry for the `cloud/*` alias names LiteLLM sends. Token usage was recorded correctly (e.g. 3528 in / 601 out) but cost was $0 because no price row matched `cloud/claude-sonnet`.
- Adding `model_info.base_model` to `litellm-config.yaml` did NOT fix it — LiteLLM still sends the alias name in OTel telemetry regardless.
- Fix: registered custom model price definitions in Langfuse via `POST /api/public/models` for all three aliases:
  - `cloud/claude-sonnet`: $3/M in, $15/M out, tokenizer=claude
  - `cloud/gemini-flash`: $0.10/M in, $0.40/M out, tokenizer=openai
  - `cloud/grok`: $0.30/M in, $0.50/M out, tokenizer=openai
- After fix, costs appear correctly per generation observation.

**Problem 2 — Disconnected LiteLLM OTel traces:**
- LiteLLM's `langfuse_otel` callback creates its own root trace per LLM call (e.g. `gherkin-specialist-llm-call`), separate from the Norma node spans.
- Fix: added `trace_id` and `parent_observation_id` to the `metadata` dict of every LiteLLM request across all 9 node files. LiteLLM uses these to nest its OTel observation under the correct Norma span.
- All nodes updated: intake, gherkin_specialist, environment_advisor, spec_advisor, spec_specialist, technical_gherkin_specialist, stage1_gate, stage2_gate, cai_gate.

**Confirmed cost for `cloud/claude-sonnet` full pipeline run (rfc2119 + openapi + jsonschema + c4):**

| Node | Input tok | Output tok | Cost |
|---|---:|---:|---:|
| spec-advisor | 1,921 | 1,442 | $0.0274 |
| technical-gherkin | 4,116 | 652 | $0.0221 |
| spec-specialist-openapi | 483 | 1,200 | $0.0195 |
| spec-specialist-c4 | 481 | 781 | $0.0132 |
| spec-specialist-rfc2119 | 481 | 607 | $0.0106 |
| spec-specialist-jsonschema | 471 | 593 | $0.0103 |
| gherkin-specialist | 551 | 443 | $0.0083 |
| environment-advisor | 625 | 402 | $0.0079 |
| intake | 232 | 442 | $0.0073 |
| **TOTAL** | | | **$0.1265** |

**Local model removal:**
- `local/qwen2.5-0.5b` was still present in `docker/litellm-config.yaml` as a dead entry. The fallback rule `{ local/qwen2.5-0.5b: [cloud/claude-sonnet] }` was also present. Both removed. Pipeline is cloud-only; local model viability is tracked separately in the local model verdict finding below.

---

## 2026-06-20 — A/B test: sonnet vs gemini-flash vs grok-3-mini

**Context:** `scripts/run_ab_test.py` — three sequential runs of the full two-stage pipeline, each with all NORMA_*_MODEL env vars set to the target model. Same requirement (REQ-001).

**Results summary:**

| Variant | Model | P1 | P2 | Wall time | Specialists | Env selected |
|---|---|---|---|---|---|---|
| sonnet | cloud/claude-sonnet | PASS | FAIL (2 revisions) | 103s | rfc2119, openapi, jsonschema, c4 | Node.js 22 / Next.js 14 |
| gemini | cloud/gemini-flash | PASS | FAIL (non-LLM) | 42s | rfc2119, openapi, json_schema | Python 3.12 / FastAPI |
| grok | cloud/grok | PASS | FAIL (structural) | 69s | (none) | JavaScript (browser) / Vanilla JS |

**Findings by variant:**

**Sonnet** — strongest spec generation. Ran 4 specialists (most thorough advice). Stage 2 Gate found a real cross-specialist inconsistency: OpenAPI and JSON Schema defined the error response shape differently (`error.message` / `error.retryable` in OpenAPI vs flat structure in JSON Schema). Gate exhausted revision limit because Technical Gherkin couldn't reconcile the inconsistency without the specs being fixed first. The gate correctly identified a real spec quality issue.

**Gemini** — fastest overall (42s). Generated valid Gherkin and valid RFC/OpenAPI/JSON Schema artefacts. Failed on a non-LLM assertion: RFC 2119 artefact did not include the `# Constraints` heading. Instruction-following gap on a format constraint that Claude follows reliably. No revision loop entered — failed on the first structural check.

**Grok** — slowest P1 (48s, Environment Advisor took unusually long). Environment Advisor selected "JavaScript (browser) / Vanilla JS" rank 1 — questionable for a greeting app that fetches external APIs. Spec Advisor produced no specialists (`spec_advice: []`) — JSON parse failure suspected (same truncation bug as before; grok-3-mini may produce more verbose output). Technical Gherkin node ran with no spec artefacts, produced output with no `Scenario` blocks — structural failure on the first assertion.

**Prompt fixes applied during this session (all variants affected):**
1. Business Gherkin `max_tokens` 800 → 1200 and line limit 60 → 80: the 800-token ceiling was crowding out required scenarios; all 3 models dropped at least one named feature.
2. Stage 1 Gate rubric: changed persona from "strict QA gatekeeper" to "business analyst"; added explicit instruction that boundary/edge-case testing is NOT required. The "strict" framing caused all 3 models to fail P1 on the first attempt by demanding exhaustive test coverage rather than named-feature coverage.

**Cross-specialist consistency** — new gap identified: Spec Advisor runs specialists in parallel with no shared schema contract for shared types. When OpenAPI and JSON Schema both define an `ErrorResponse`, they can independently produce inconsistent shapes. This is a pipeline design gap, not a model quality gap.

**Verdict:** Sonnet is the only model that produced all specialists correctly and found real spec issues. Gemini is viable for P1 and shows potential for cost reduction once the RFC heading instruction is fixed. Grok is not yet viable for this pipeline — fails at Environment Advisor quality, Spec Advisor JSON output, and Technical Gherkin generation.

---

## 2026-06-20 — REQ-004 second run (all fixes applied)

**Context:** Full run after tightening Business Gherkin, reworking Technical Gherkin as standalone, updating Stage 2 Gate rubric, and adding dated output folders.

**Result:** PASS/PASS — 61.4s total (P1: 18.4s, P2: 43.0s). Both gates passed on first attempt with zero revisions.

**Specialists selected:** `rfc2119`, `c4`, `adr` (no OpenAPI — Spec Advisor read the CLI environment signal and correctly excluded HTTP contracts for a terminal app).

**Environment selected:** Python 3.12 / Click (CLI), rank 1. Appropriate for a single-user greeting app with no web layer.

**Stage 1 Gate fix:** First run of this session failed because the LLM produced a verbose markdown checklist instead of the required `PASS` / `FAIL: <one sentence>`. Root cause: system prompt said "No other output" but did not explicitly forbid reasoning. Fix: replaced with "no reasoning, no markdown" phrasing; bumped `max_tokens` 256 → 512 to avoid truncation of legitimate FAIL explanations.

**Artefacts:** `req_001.feature`, `req_001.environments.json`, `req_001.technical.feature`, `req_001.rfc2119.md`, `req_001.c4.md`, `req_001.adr.md` — all written to `output/2026-06-20/093244/`.

---

## 2026-06-20 — REQ-004 first two-stage run

**Context:** First end-to-end run of Pipeline 1 + Pipeline 2 via `scripts/run_full.py`.

**Pipeline 1 result:** PASS. Stage 1 Gate passed on first attempt.
- Environment Advisor produced 3 options (Node.js 22/Express rank 1, Python 3.12/FastAPI rank 2, Node.js 22/Next.js rank 3). Rationale was requirement-specific and correct.
- Stage 1 Gate: Gherkin business coverage rubric → PASS.

**Pipeline 2 result:** PASS. Stage 2 Gate passed on first attempt.
- Spec Advisor bug found and fixed (see below). After fix, specialists expected: RFC 2119 + OpenAPI.
- Technical Gherkin Specialist produced 13 344 chars of enriched Gherkin.
- Stage 2 Gate: structural checks + coverage rubric → PASS.

**Bug: Spec Advisor silently dropped all recommendations (specialist_count: 0).**
- Root cause: LLM output for 2 specialists with verbose `requirement_segments` + `insight` + `statement` fields exceeded `max_tokens: 1500`, producing truncated invalid JSON. `_parse_advice` silently returns `[]` on JSON parse failure.
- Fix: tightened field-length constraints in the CRISPE `statement` field — each of `rationale`, `requirement_segments`, `role`, `insight`, `statement` now has an explicit line/sentence limit. The example in the prompt was updated to model concise output.
- Do NOT raise `max_tokens` — fix the prompt instead (per project discipline).
- Downstream effect: Technical Gherkin Specialist ran with no spec artefacts (`gherkin-only` mode), so `gherkin_technical` was enriched only from business Gherkin. Re-run needed to validate the full specialist chain.

---

## 2026-06-16 — Full stack connectivity verified

**Langfuse v3** (self-hosted) and **LiteLLM gateway** pass their full connectivity test suites (`scripts/test_langfuse.py`, `scripts/test_litellm.py`):

- Langfuse: health, auth, trace/span ingestion, score ingestion, dataset ops, prompt management, REST batch ingestion — all green.
- LiteLLM: all cloud model endpoints healthy.

**Fix applied:** `gemini/gemini-2.0-flash-lite` was permanently retired by Google (HTTP 404). Migrated to `gemini/gemini-2.5-flash-lite`, which is the direct successor and confirmed working.

---

## 2026-06-19 — REQ-001 T2: Gherkin Specialist trace analysis

**Context:** Standalone run of the Gherkin Specialist node (before full pipeline wiring).

**Model fallback observed:** `local/phi3-mini` silently fell back to `cloud/claude-sonnet`. LiteLLM's 30s `request_timeout` triggered for phi3-mini; the configured fallback `{ local/phi3-mini: [cloud/claude-sonnet] }` kicked in. Same failure mode as the Intake node (T1). Root cause: CPU-only host cannot serve phi3-mini within 30s under load.

**Output truncated at 1024 tokens:** The final scenario was cut mid-sentence. `max_tokens=1024` too tight for a 6–7 scenario feature file. Fixed: raised to 2048 in the node.

**Wall time ~79s breakdown:**
- ~30s waiting for phi3-mini to timeout
- ~16s Claude Sonnet inference (Langfuse latency: 15.958s)
- ~33s httpx/Langfuse flush overhead

**Token counts:** 340 prompt tokens, 1024 completion tokens (capped), 1364 total. Cost: ~$0.016/run.

**Non-determinism:** scenario count varied 6 vs 7 between runs at `temperature=0.2`. Expected for generative tasks; CAI gate catches structural gaps.

**Trace naming:** LiteLLM's OTel integration creates a root trace named `gherkin-specialist-llm-call` separate from the Norma `gherkin_specialist` span. Span tree unified properly in T4 when the full graph ran under a single Langfuse trace.

---

## 2026-06-19 — REQ-001 T4: Full pipeline end-to-end run

**Context:** First run of the complete 3-node pipeline (INTAKE → GHERKIN SPECIALIST → CAI GATE).

**Result:** PASS. CAI gate passed on first attempt. Artefact: valid `.feature` file covering time-of-day greeting, content choice, and error path.

**All nodes required `cloud/claude-sonnet`:** Local models (qwen2.5-0.5b, phi3-mini) either failed structured-output format-following or hit LiteLLM's 30s timeout. This is a CPU-only host limitation, not a model capability limitation per se.

**Cost per run:** ~$0.016–$0.020 (all-cloud config).

**Span tree:** Unified correctly under a single Langfuse trace once the full graph ran. Node spans (intake, gherkin_specialist, cai_gate) appear as children of the root trace.

---

## 2026-06-19 — REQ-001 build evaluation: Claude Code vs Gemini

**Context:** REQ-001 Gherkin spec (`output/req_001.feature`) was handed to two AI code assistants independently with no additional context.

**Claude Code:** Built a working Flask app with correct greeting logic (all 4 time bands, correct boundaries), auth vs anonymous handling, real API integrations (zenquotes.io, official-joke-api), error handling with retry, and parametrized pytest covering all 12 time examples from the spec. Tests pass.

**Gemini:** Generated a Behave scaffold with a boilerplate counter scenario unrelated to the spec. Did not implement the app.

**Signal:** Gemini had no context beyond the feature file and could not proceed. Claude Code succeeded but only by making its own assumptions on tech stack, API endpoints, timeout values, and retry limits — none of which were in the spec.

**Conclusion:** The Gherkin spec is necessary but not sufficient. Non-functional requirements (NFRs) are the missing layer. Without them, implementation quality depends on the assistant's willingness to guess — not on the spec's correctness.

**Next step:** Add an NFR Specialist node to the pipeline (→ REQ-002).

---

## Local model verdict (2026-06-19)

**Conclusion: local inference is not viable on this host for structured output tasks.**

- `qwen2.5:0.5b` (1.2 GB RAM): too small for format-following on any Norma task
- `phi3-mini` (3.8B): hits LiteLLM's 30s `request_timeout` consistently on CPU-only hardware

Local models have been removed from LiteLLM config and `.env.example`. All nodes default to `cloud/claude-sonnet`. If the host hardware changes, revisit — but don't engineer around the constraint that doesn't exist.

**Smaller cloud models** (grok-3-mini, gemini-flash) remain available via LiteLLM aliases and are worth evaluating for cost reduction on less demanding nodes (e.g., intake classification).
