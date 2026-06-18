# Norma — Vision

---

## What Norma Is

Norma is a **PEF-compliant requirement processor**.

It takes a natural language requirement and runs it through a pipeline of named, composable Prompt Engineering Framework (PEF) compositions. The output is a spec bundle: machine-readable, human-validatable documents in industry-standard languages.

The spec bundle is not a target — it is the natural outcome. A simple requirement produces Gherkin. A system with events, APIs, and decisions produces AsyncAPI + OpenAPI + Gherkin + MADR + C4 DSL. The depth of output scales with the complexity of the input. Norma does not decide the output set — the requirement does.

---

## The Spec is the Contract

The emitted spec bundle is the authoritative contract for everything downstream. No build agent, code assistant, or human implementation is authoritative over it.

The spec is:
- **Machine-readable** — parseable by tools, agents, and code assistants without interpretation
- **Human-validatable** — a developer can read it and confirm it captures intent
- **Industry-standard** — each artefact uses an established spec language with known semantics

---

## PEF: Layered and Composable

All prompts inside Norma are assembled from named PEF components — COSTAR, CRISPE, CAI. No ad-hoc strings anywhere in the codebase.

PEF compositions are themselves layered and composable. Simpler requirements invoke simpler compositions. Richer requirements invoke deeper combinations. The granularity of the output spec emerges from the composition depth, not from hard-coded output targets.

---

## Validation Loop

Norma's spec quality is validated by attempting to build the described system from the spec alone.

```
Requirement
    ↓
Norma  (PEF-compliant processor)
    ↓
output/specs/     ← spec bundle (machine-readable, human-validatable)
    ↓
Claude Code       ← builds app from spec, no prior context
    ↓
output/build/     ← generated application
    ↓
Human runs it     ← does it satisfy the original requirement?
    ↓
Conformance check ← Claude Code reviews generated app against spec
    ↓
Refinement signal ← back into Norma PEF compositions
```

**The quality signal:** If Claude Code reads the spec and builds a working app with no clarification questions, the spec was good. If it asks questions, makes wrong assumptions, or the built app fails — the spec was incomplete. That is a Norma failure, and the refinement targets the responsible PEF composition.

**Human-in-the-loop is intentional.** Automating the build-and-verify step via LLM API comes after the signal is consistent enough to encode as assertions. Not before.

---

## What Norma Is Not

- A code generator — it generates specs, not applications
- A build system — the build is downstream, owned by the code assistant
- A test runner — the CAI gate validates spec structure; the build validation is done externally
- A local inference system — cloud models via LiteLLM are the inference tier; local model routing is not a design goal on current hardware

---

## Key Invariants

- **No ad-hoc prompts** — every prompt is assembled from named PEF components
- **CAI gate is not optional** — every artefact passes the gate before emission
- **LiteLLM is the only inference endpoint** — Norma never calls providers directly
- **Observation is automatic** — Langfuse traces every node; every run is inspectable
- **Output scales with input complexity** — the spec bundle depth is determined by the requirement, not by configuration
