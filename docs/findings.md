# Norma — Run Findings

Observations from pipeline runs. Updated after each significant run or trace analysis session.
The format: what happened, what the numbers were, what it means going forward.

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
