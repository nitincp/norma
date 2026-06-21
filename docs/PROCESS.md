# Norma — Process

How this project gets built and iterated.

---

## Role: Composer / Observer

Claude acts as composer and observer — not predictor.

- Pipeline runs. Output is not anticipated.
- Output arrives. Validate: did it meet the spec contract?
- Traces open (Langfuse). Analyse what happened inside.
- Refine PEF compositions based on observation, not assumption.

No pre-validating what a node "should" produce. Let the prompts work. The dark part (inside the pipeline) is analysed after the process completes. Inject PEF refinements based on what traces and artefacts reveal.

---

## Build Philosophy: YAGNI + KISS

- Start with the smallest pipeline that can close a loop end-to-end.
- Add nodes, spec languages, and complexity only when the current loop is proven and boring.
- Three nodes that work beats five nodes that are planned.

---

## Iteration Rhythm

```
1. Pick smallest open task
2. Build it (one node, one prompt, one assertion)
3. Run it
4. Observe: Langfuse traces + artefact output
5. Validate: did the CAI gate pass?
6. Refine: adjust one PEF field if needed, re-run
7. When the loop closes cleanly → it's boring → stop
8. Move to next task, or next requirement, or next harder challenge
```

**Stop condition:** Loop closes on first or second attempt with no interesting failure — that unit is done. Don't polish. Move forward.

**Escalation condition:** Fails to close after 2–3 refinement cycles — surface the failure explicitly. The failure is the data. Record it in [findings.md](findings.md), analyse traces, then decide: refine prompt or restructure node.

---

## Validation Rhythm (spec → build → verify)

After a requirement closes through the Norma pipeline:

```
1. Norma emits spec bundle to output/specs/
2. Claude Code builds app from spec (output/build/) — no prior context, spec only
3. Human runs the built app
4. Human reports: did build go smoothly? Does the app work?
5. Claude Code reviews generated app against spec for conformance
6. Refinement signal identified → targets responsible PEF composition
```

This is the integration test for Norma's spec quality. If the code assistant needs to ask clarifying questions or makes wrong assumptions, the spec was incomplete — that is a Norma failure.

---

## Token Budget Discipline

`max_tokens` per node is a hard ceiling, not a dial.

- Set the ceiling to match what a minimal correct output should need.
- If output truncates, tighten the prompt (add a word/line limit, narrow scope) — do not raise the ceiling.
- Token costs compound: a node that is verbose on a simple app will be unmanageable on a complex one.

**Rule:** prompt controls verbosity; `max_tokens` enforces the contract.

---

## Prompt Management

All prompts live in `prompts/*.yaml` as the canonical source of truth. The pipeline fetches them from Langfuse at runtime.

**Workflow for any prompt change:**

```
1. Edit the relevant prompts/*.yaml file
2. uv run python scripts/seed_prompts.py <node>   # push new version to Langfuse
3. uv run python scripts/run_<node>.py            # smoke test the node in isolation
4. Observe the Langfuse trace — the trace is now linked to the exact prompt version
5. uv run python scripts/run_full.py              # end-to-end if node smoke test passes
```

Each `seed_prompts.py` call creates a new versioned prompt in Langfuse labelled `production`. Prior versions are preserved. Every Langfuse trace links to the exact prompt version that produced it — use this when analysing a bad trace.

**File → Langfuse name mapping:**

| YAML file | Langfuse name | Node |
|---|---|---|
| `prompts/intake.yaml` | `norma.intake` | intake |
| `prompts/gherkin_specialist.yaml` | `norma.gherkin_specialist` | gherkin_specialist |
| `prompts/environment_advisor.yaml` | `norma.environment_advisor` | environment_advisor |
| `prompts/stage1_gate.yaml` | `norma.stage1_gate.rubric` | stage1_gate (assertion 2 only) |
| `prompts/spec_advisor.yaml` | `norma.spec_advisor` | spec_advisor |
| `prompts/spec_specialist_shell.yaml` | `norma.spec_specialist_shell` | spec_specialist |
| `prompts/technical_gherkin_specialist.yaml` | `norma.technical_gherkin_specialist` | technical_gherkin_specialist |
| `prompts/stage2_gate.yaml` | `norma.stage2_gate.rubric` | stage2_gate (assertion 2 only) |
| `prompts/cai_gate.yaml` | `norma.cai_gate.rubric` | cai_gate (assertion 3 only) |

**Spec Specialist note:** `role`, `insight`, and `statement` are injected at runtime from the Spec Advisor's recommendation — only `capacity`, `personality`, and `experiment` come from Langfuse. The two-phase statement prefix (`## EXAMPLE / ## ARTEFACT`) lives in code because it wraps a runtime value (`{language}`).

**Gate notes:** Stage 1 and Stage 2 gate assertion 1 checks are non-LLM structural checks (not seeded). Only the LLM rubric (assertion 2) is in YAML/Langfuse. Same applies to CAI gate assertion 3.

---

## PEF Refinement Loop

All prompts are PEF compositions (COSTAR, CRISPE, CAI). Refinements follow this pattern:

1. Edit the YAML — one field only
2. Seed: `uv run python scripts/seed_prompts.py <node>`
3. Run: smoke test or full pipeline
4. Observe: Langfuse trace linked to the new prompt version
5. Compare output quality vs prior version

No rewriting whole prompts. Surgical field edits, observed effect.

---

## Expansion Triggers

| Signal | Action |
|---|---|
| Gate passes first attempt | Loop is closed, move on |
| Gate passes after 1 revision | Note what the gate caught, refine Specialist prompt |
| Gate fails after 2 revisions | Escalate — analyse traces, restructure node or prompt |
| Built app works first time | Spec quality confirmed, move to next requirement |
| Built app fails or needs clarification | Spec was incomplete — refine the responsible PEF composition |
| Requirement fully spec'd, boring | Pick next requirement (harder scope) |
| Cloud model costs too high on a node | Switch to cheaper cloud alias (`cloud/grok`, `cloud/gemini-flash`) |

---

## Model Assignment

All nodes default to `cloud/claude-sonnet`. Cheaper cloud aliases (grok-3-mini, gemini-flash) are available via LiteLLM and worth evaluating for less demanding nodes once the pipeline is stable.

Local model inference is not a design goal on current hardware — see [findings.md](findings.md).

| Node type | Default | Candidate for cost reduction |
|---|---|---|
| Classification / intake | `cloud/claude-sonnet` | `cloud/grok` or `cloud/gemini-flash` |
| Spec generation | `cloud/claude-sonnet` | evaluate after quality baseline established |
| CAI gate / judge | `cloud/claude-sonnet` | stays cloud, judge quality matters |
