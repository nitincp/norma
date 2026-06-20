# Norma — Prompt Engineering Framework (PEF) Design Principles

Guidelines for composing prompts across all Norma nodes. These are hard-won rules — each one tracks back to an observed failure mode.

---

## Principle 1 — Self-anchoring two-phase output

**What it is:**  
For any node that produces structured output (a schema, a format with required headings, a JSON contract), instruct the model to generate a short canonical example of the target structure *before* writing the actual artefact.

**Why it works:**  
Models pattern-match on their own recent output. A model that just wrote `# Constraints` as part of its own example cannot coherently omit it two lines later. The example becomes an in-context scaffold — format knowledge the model already holds is made explicit and active before it commits to content. This is more reliable than abstract rules ("you MUST include…") because the model has demonstrated the structure to itself.

**Two-phase instruction template (for CRISPE `statement` field):**

```
Step 1 — Before writing anything, produce a [N]-line canonical example 
of a well-formed [output_type] showing the required structure, headings, 
and any mandatory keywords or fields.

Step 2 — Using that example as your scaffold, produce the full output 
for the content below.
```

**Candidate nodes — apply this principle:**

| Node | Output type | Risk without anchoring | Status |
|---|---|---|---|
| Spec Specialist | Spec artefact per type (RFC 2119, OpenAPI, JSON Schema, C4, …) | Missing required headings/sections; format varies by type so "forgotten" structure is common | REQ-005 T3 |
| Spec Advisor | JSON array of `SpecAdvice` objects | JSON truncation + parse failure; model skips required fields | REQ-005 T4 |
| Gherkin Specialist | `.feature` file (Feature / Scenario / Given/When/Then) | Dropped scenarios; missing coverage; incomplete steps | Apply after T3/T4 validated |
| Technical Gherkin Specialist | `@technical`-only `.feature` file | Missing `@technical` tag; business scenarios leaking in; incomplete steps | Apply after T3/T4 validated |
| Environment Advisor | JSON array of ranked `EnvironmentOption` objects | Unrealistic rank-1 selection; missing required fields in JSON | Apply after T3/T4 validated |

**Not applicable:**

| Node | Reason |
|---|---|
| Stage 1 Gate | Output is PASS/FAIL — too short to anchor; rubric clarity is the lever |
| Stage 2 Gate | Same |
| CAI Gate | Same |
| Intake | Prose normalisation — no strict format contract |

---

## Principle 2 — Separation of format and content knowledge

**What it is:**  
Format knowledge (what a valid RFC 2119 doc looks like, what JSON Schema syntax requires) lives in the node that produces the artefact, not in the node that recommends it.

**Rule:** Spec Advisor recommends *what and why*. Spec Specialist owns *how to structure the output*. Never put format instructions or examples in the Advisor.

**Why it matters:**  
The Advisor is already the highest-risk node for JSON truncation. Adding format generation to its output makes the JSON heavier. Format knowledge is also stable across requirements — a `# Constraints` heading is always a `# Constraints` heading regardless of domain. Content knowledge is requirement-specific and belongs in `insight` / `requirement_segments`.

---

## Principle 3 — No ad-hoc prompts

All prompts are assembled from named PEF components (`COSTAR`, `CRISPE`). No inline prompt strings in node files. Every field in a PEF composition is a single-purpose string — surgical edits only, never full rewrites.

---

## Principle 4 — max_tokens is a hard ceiling, not a buffer

Truncated output is a prompt failure, not a token budget failure. When output is too long or gets cut off:
- Tighten field-length constraints in the `statement` field
- Add explicit per-field sentence/line limits to the CRISPE
- Use `experiment` field to model concise output

Never raise `max_tokens` to fix a verbosity problem.

---

## Principle 5 — Single-field surgical edits

When a node produces wrong output, identify the single CRISPE field responsible and edit only that field. Full prompt rewrites destroy the ability to attribute cause to a specific change. Iteration rhythm: one field edit → run → observe gate result → next edit if needed.

---

## Principle 6 — Quirk discovery via reverse prompting

When a node fails a structural assertion and single-field PEF edits don't close the gap, feed the desired output (a Sonnet PASS artefact) to the failing model and ask: *"What system prompt would reliably produce this output from you? Be specific about format constraints, persona, and output discipline."* Apply the suggested delta as a surgical CRISPE field edit and re-run. Cap at `MAX_QUIRK_CYCLES = 3`. Outcomes are binary: **pass** (done, discard the cycle log) or **quirk found** (characterised failure mode + the CRISPE delta that addresses it, recorded in `findings.md`).

This process is not yet implemented as a script — it is currently a manual trace-inspection exercise.

---

## Principle 7 — Quirk registry and injection (planned)

Characterised quirks from Principle 6 are stored in a **quirk registry** (`findings.md` until formalised): per-model, per-node entries of the form `(model_alias, node_name) → CRISPE field override`. At runtime, a `MODEL_TWEAKS` dict applies these overrides on top of the canonical base CRISPE before the LLM call. The base prompt stays model-agnostic; model-specific deltas are explicit, localised, and version-controlled separately.

Neither the registry store nor the runtime injection is implemented yet.
