# Norma — Project Execution Model

How this project gets built and iterated.

---

## Role: Composer / Observer

Claude acts as composer and observer — not predictor.

- Pipeline runs. Output is not anticipated.
- Output arrives. Validate: did it meet the spec contract?
- Traces open (Langfuse). Analyse what happened inside.
- Refine prompt engineering compositions based on observation, not assumption.

**What this means in practice:** No pre-validating what a node "should" produce. Let the prompts and agents work. The dark part (inside the pipeline) is analysed after the process completes. Inject PEF refinements based on what the traces and artefacts reveal.

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
6. Refine: adjust PEF composition if needed, re-run
7. When the loop closes cleanly → it's boring → stop
8. Move to next task, or next requirement, or next harder challenge
```

**Stop condition:** If a loop closes on the first or second attempt with no interesting failure — that unit is done. Don't polish. Move forward.

**Escalation condition:** If a unit fails to close after 2–3 refinement cycles, surface the failure explicitly. The failure is the data — record it, analyse traces, then decide: refine prompt or restructure node.

---

## Prompt Engineering Refinement Loop

All prompts are PEF compositions (COSTAR, CRISPE, PersonaLayer, CAI). Refinements follow this pattern:

1. Run with current composition
2. Observe output quality + gate result
3. Identify which PEF field caused the issue (too vague Objective? wrong Audience? missing Constraint?)
4. Adjust that field only — one variable at a time
5. Re-run, compare

No rewriting whole prompts. Surgical field edits, observed effect.

---

## Expansion Triggers

| Signal | Action |
|---|---|
| Gate passes first attempt | Loop is closed, move on |
| Gate passes after 1 revision | Note what the gate caught, refine Specialist prompt |
| Gate fails after 2 revisions | Escalate — analyse traces, restructure node or prompt |
| Requirement fully spec'd, boring | Pick next requirement (harder scope) |
| Local model output consistently poor on a node | Promote that node to cloud model, note in config |
| Cloud model overkill on a node | Demote to local, reduce cost |

---

## Model Assignment Defaults

| Node type | Default model | Promote to |
|---|---|---|
| Classification / intake | `local/qwen2.5-0.5b` | `local/phi3-mini` |
| Spec generation | `local/phi3-mini` | `cloud/claude-sonnet` |
| CAI gate / judge | `cloud/claude-sonnet` | — (judge stays cloud) |
| MADR decisions | `cloud/claude-sonnet` | — (judgment stays cloud) |
