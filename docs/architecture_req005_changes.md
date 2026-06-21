# Architecture Delta — REQ-005

**REQ:** REQ-005 — Node quality baseline, granular execution, cross-model consistency  
**Status:** In progress (T1–T4 done, T5–T6 pending)  
**Merge into ARCHITECTURE.md when:** REQ-005 closes (all tasks done)  
**Delete this file after merge.**

---

## Workflow changes

### Granular execution — new path alongside full pipeline (T1, applied)

Current architecture has one execution path: full pipeline end-to-end. REQ-005 adds a second path for targeted node iteration.

```mermaid
flowchart LR
    F[tests/fixtures/\nstate_*.json] -->|load snapshot| RN[run_node.py\nnode + snapshot]
    RN -->|state diff| OUT([terminal output])
    RN -->|--save| SNAP([snapshot.out.json])

    P1[Pipeline 1] -->|run_pipeline2.py| P2[Pipeline 2]
    P1 -.->|save checkpoint| F
```

### Pipeline 2 — shared_types contract (T5, pending)

Current Pipeline 2: Spec Advisor fans out to specialists with no shared contract. Each specialist independently defines types like `ErrorResponse`, causing cross-artefact inconsistency caught only at Stage 2 Gate.

**Current:**

```mermaid
flowchart LR
    SA[Spec Advisor\nspec_advice] -->|Send × N\nrole · insight · statement| SS[Spec Specialist × N]
    SS -->|fan-in| TGS[Technical Gherkin Specialist]
```

**After T5:**

```mermaid
flowchart LR
    SA[Spec Advisor\nspec_advice\n+ shared_types] -->|Send × N\nrole · insight · statement\n+ shared_types contract| SS[Spec Specialist × N]
    SS -->|fan-in| TGS[Technical Gherkin Specialist]
```

`shared_types[]` is a pre-agreed list of type names emitted by the Spec Advisor and injected into every specialist's `insight` field before they run in parallel. Specialists reference the contract, not define it independently.

---

## Changes applied (T1–T4)

### Execution paths — new: single-node runner (T1)

New script `scripts/run_node.py` enables running any node in isolation against a saved state snapshot. Changes to the Execution paths section:

- Add **Single node** subsection with `run_node.py` usage, `--save` flag, and model override pattern
- Add fixture table (`tests/fixtures/`) with one row per snapshot

### Test suite — new section (T2)

New section added to ARCHITECTURE.md covering:
- 57 tests total, split by file with LLM test counts
- `@pytest.mark.llm` marker — skip with `-m 'not llm'`
- Test philosophy (non-LLM assertions as primary target; gate structural assertions as ground truth)
- "Adding tests for a new node" checklist

### SPEC SPECIALIST node — statement field behaviour changed (T3)

The `statement` CRISPE field is no longer passed through verbatim from the Spec Advisor recommendation. It is now prefixed at runtime with a two-phase instruction:

- Phase 1: model generates a 4–6 line canonical example of the target spec format (`## EXAMPLE`)
- Phase 2: model uses that example as scaffold to write the full artefact (`## ARTEFACT`)

Node extracts only the `## ARTEFACT` section from the response. Falls back to full response if label absent.

Update to node entry in ARCHITECTURE.md:

> **Statement field:** prefixed at runtime with a two-phase self-anchoring instruction (see PEF.md Principle 1). The Spec Advisor's format rules are appended after the prefix — the model sees both.

### SPEC ADVISOR node — input changed + one-shot anchoring added (T4)

**Input change:** Spec Advisor no longer receives Business Gherkin. It now reads `normalised_requirement` + `selected_environment` only.

Rationale: Spec Advisor makes an architectural decision (which spec languages), not a behavioural one. Business Gherkin is the behaviour layer and adds noise without changing the spec-language decision. The normalised requirement + environment choice carries all necessary structural signal (external APIs, data contracts, deployment constraints).

State keys consumed by Spec Advisor:

| Before | After |
|---|---|
| `normalised_requirement`, `gherkin_business`, `selected_environment` | `normalised_requirement`, `selected_environment` |

**One-shot anchoring:** A concrete JSON example is now embedded in the `statement` field of `prompts/spec_advisor.yaml`. The example shows one fully-populated `SpecRecommendation` object so the model pattern-matches on the exact schema before generating its own output.

**Field length limits added:** Hard word-count limits per field prevent JSON truncation at the `max_tokens` ceiling:

| Field | Limit |
|---|---|
| `rationale` | ≤ 15 words |
| `requirement_segments` | ≤ 20 words |
| `role` | ≤ 15 words |
| `insight` | ≤ 3 bullet points × ≤ 8 words each |
| `statement` | ≤ 3 lines |

Root cause of prior silent failures: when 4–5 verbose specialists were generated, output exceeded 1500 tokens, producing truncated JSON which `_parse_advice` silently returned `[]` for.

**All 9 nodes now wired to Langfuse prompt fetch.** Four nodes were still using hardcoded prompts (`environment_advisor`, `technical_gherkin_specialist`, `stage1_gate`, `stage2_gate`). All now follow the same pattern: fetch prompt from Langfuse at runtime, cache for 300 s. Four new YAML prompt files created:

| YAML | Langfuse name | Node |
|---|---|---|
| `prompts/environment_advisor.yaml` | `norma.environment_advisor` | environment_advisor |
| `prompts/stage1_gate.yaml` | `norma.stage1_gate.rubric` | stage1_gate (LLM rubric only) |
| `prompts/stage2_gate.yaml` | `norma.stage2_gate.rubric` | stage2_gate (LLM rubric only) |
| `prompts/technical_gherkin_specialist.yaml` | `norma.technical_gherkin_specialist` | technical_gherkin_specialist |

**Run output: cost + token tracking added.** `scripts/output_utils.py` gains `fetch_run_usage()` — queries `GET /api/public/observations` on the Langfuse API after the run completes, sums `usage.input`, `usage.output`, and `calculatedTotalCost` across all observations with `usage.total > 0`. Patched into `run_summary.json` as `prompt_tokens`, `completion_tokens`, `cost_usd`. Console now shows: `Total: Xs — $X.XXXX (N in / N out)`.

**Normalised requirement now written to output folder.** `req_001.normalised.txt` is written alongside the other P1 artefacts in `output/YYYY-MM-DD/HHMMSS/`.

---

## Changes pending (T5–T6)

### T5 — SPEC ADVISOR output — new `shared_types[]` field

`SpecRecommendation` gains a `shared_types[]` field: type names that multiple specialists will reference (e.g. `ErrorResponse`). Spec Advisor populates it; each specialist receives it in the `insight` field as a pre-agreed contract.

**State delta:**

| Key | Change |
|---|---|
| `spec_advice[].shared_types` | New field on `SpecRecommendation` — list of shared type names |

**Node delta — SPEC ADVISOR:**
> Also emits `shared_types[]` per recommendation — type names pre-agreed across specialists.

**Node delta — SPEC SPECIALIST:**
> Receives `shared_types` via `insight` field: *"The following shared types are pre-agreed: {shared_types}. Use these exact names and shapes."*

**Why this matters for the architecture:** Stage 2 Gate currently catches cross-artefact type inconsistency as a symptom. T5 fixes the root cause — no shared contract during parallel fan-out. After T5, the gate validates conformance to a contract that was established before specialists ran.

### T6 — No architecture change

A/B re-run across all three models. Results go to `findings.md`. No structural change to nodes, state, or pipelines.
