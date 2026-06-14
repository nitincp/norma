# Norma — Requirements Document

> **Purpose:** This document is the single source of truth for building Norma from scratch.
> It replaces the need to carry any prior research artifacts into the new repo.

---

## 1. What Norma Is

Norma generates structured, machine-readable specs from natural language requirements.
Specs drive development — either via an automated build layer or by feeding a code assistant.

The name reflects the core invariant: everything built must conform to a **norm** (industry standard spec language). The spec is the carpenter's square.

---

## 2. Objective

```
Requirement (natural language)
        ↓
  [ Norma ]
        ↓
Spec (layered, composable, industry-standard)
        ↓
  ┌─────────────────┐
  │ Option A        │  Build layer — agents execute against the spec
  │ Option B        │  Code assistant — reads spec, builds the application
  └─────────────────┘
```

Specs are **layered and composable**:
- A requirement may produce multiple spec artefacts (e.g., an API contract + a data schema + a behaviour spec)
- Each artefact is in the best-fit industry standard language for that layer
- Specs reference each other; the composition is the full system spec

---

## 3. Spec Languages (Target Set)

| Layer | Language | Use |
|---|---|---|
| API contracts | OpenAPI 3.1 | REST surface, request/response schemas |
| Async / event contracts | AsyncAPI 2.x | Event-driven surfaces, message schemas |
| Data shape | JSON Schema | Shared types, payload validation |
| Behaviour / acceptance | Gherkin (`.feature`) | Given/When/Then acceptance criteria |
| Architecture decisions | MADR (ADR format) | Decisions that constrain implementation |
| System context | C4 DSL (Structurizr) | Component and container boundaries |

New languages are added as the domain demands — the list is open, not fixed.

---

## 4. Principals

### 4.1 Grounded in Prompt Engineering Frameworks (PEF)

All prompts in Norma are composed from named, reusable prompt engineering frameworks.
No ad-hoc prompt strings anywhere in the codebase.

Baseline frameworks carried forward from prior work:
- **COSTAR** — Context · Objective · Style · Tone · Audience · Response
- **CRISPE** — Capacity · Role · Insight · Statement · Personality · Experiment
- **PersonaLayer** — Persona identity injected before task framing
- **ConstitutionalAI gate** — Output validation before any artefact is emitted

### 4.2 Composition in Layers

Prompts are assembled at runtime from discrete, single-responsibility components:

```
Persona → Task → Context → Constraints → Output Format
```

Each component is a named PEF block. Composition is explicit and traceable in Langfuse spans.
No component bleeds into another's responsibility.

### 4.3 Effectiveness Through Observation → Reflection → Output

Norma improves through a closed loop:
1. **Observation** — Langfuse traces capture every node execution, token count, and spec artefact emitted
2. **Reflection** — Promptfoo evals assert spec quality (completeness, unambiguity, standard conformance)
3. **Output** — Build quality and usability of emitted specs are the ground truth signal

Dynamic meta-prompting (Spec Advisor generating prompts for Spec Specialist at runtime) emerges naturally from this loop. It is an observation, not a design objective at this stage.

---

## 5. Architecture

### 5.1 Tier Model

```
TIER 3 — Orchestration      LangGraph (Python)
TIER 2 — Routing / Gateway  LiteLLM
TIER 1 — Observability      Langfuse (self-hosted) + Promptfoo (evals)
TIER 0 — Inference          Ollama (local, CPU-only) + Cloud API (Anthropic / OpenAI via LiteLLM)
```

### 5.2 Why This Stack

| Decision | Rationale |
|---|---|
| LangGraph over AutoGen / CrewAI | Explicit state machine; deterministic transitions; checkpointing maps 1:1 to Langfuse spans; lowest idle CPU footprint (~18 MB) |
| LiteLLM | Native Ollama routing; async connection pooling prevents CPU thrashing when Tier 0 saturates; unified OpenAI-spec endpoint abstracts provider |
| Langfuse (self-hosted) | Traces every LangGraph node as a parent-child span tree; port-forwarded at `localhost:3000`; already proven in prior environment |
| Promptfoo | Headless CLI eval engine; YAML-driven LLM-as-judge assertions; exploits NVMe sequential write; no web browser required for CI |
| Ollama (local) | CPU-only; `qwen2.5:0.5b` (~1.2 GB RAM) for fast validation passes; `phi3-mini` (3.8B) for deeper reasoning when RAM permits |
| Cloud API fallback | Anthropic Claude Sonnet / OpenAI GPT-4o via LiteLLM virtual keys for tasks that exceed local model capability |

### 5.3 Environment Constraints

- Headless Linux VM, CPU-only (no GPU/VRAM)
- NVMe 2.4 GB/s sequential read/write
- VS Code over SSH; Langfuse UI via port tunnel `localhost:3000`
- Ollama at `0.0.0.0:11434`; `OLLAMA_NUM_PARALLEL=1` (mandatory to prevent CPU thrashing)
- LiteLLM `request_timeout=30s`; `max_concurrent_requests=2`

### 5.4 DevContainer Topology

```
[ WINDOWS CLIENT HOST ]
  └── VS Code (SSH)
        └── Port tunnels → localhost:3000 (Langfuse) · localhost:11434 (Ollama)
                │
      (SSH loop)
                │
[ HEADLESS LINUX VM ]
  └── Docker / DevContainer
        ├── app-runtime       (LangGraph agent graph)
        ├── litellm-gateway   (Tier 2 routing, virtual keys)
        ├── langfuse-server   (Tier 1 traces, self-hosted)
        └── ollama-inference  (Tier 0, CPU-pinned)
```

---

## 6. Core Graph Design

```
Requirement (string)
        ↓
┌─────────────────────────────┐
│  INTAKE NODE                │  Normalise and classify the requirement
│  Framework: COSTAR          │
└────────────┬────────────────┘
             ↓
┌─────────────────────────────┐
│  SPEC ADVISOR NODE          │  Decide which spec languages apply; generate
│  Framework: CRISPE          │  runtime prompts for each Spec Specialist instance
└────────────┬────────────────┘
             ↓ (parallel edges per spec language)
┌─────────────────────────────┐
│  SPEC SPECIALIST NODE(s)    │  Receive generated prompt; emit spec artefact
│  Framework: CRISPE (generated at runtime by Spec Advisor)
└────────────┬────────────────┘
             ↓
┌─────────────────────────────┐
│  CONSTITUTIONAL AI GATE     │  Validate each artefact: completeness,
│  Eval: Promptfoo assertion  │  standard conformance, unambiguity
└────────────┬────────────────┘
             ↓ (proceed / revise / reject)
┌─────────────────────────────┐
│  COMPOSER NODE              │  Assemble artefacts into layered spec bundle;
│                             │  emit cross-references between layers
└────────────┬────────────────┘
             ↓
     Spec Bundle Output
```

The `revise` edge loops back to the Spec Specialist with the gate's feedback.
The `reject` edge escalates to the Spec Advisor for prompt regeneration.

---

## 7. Output Options

### Option A — Build Layer
Norma's Composer emits specs into a build-layer agent graph that:
- Reads the spec bundle
- Scaffolds code, tests, and infrastructure conforming to the spec
- Reports conformance back as a build quality signal to Promptfoo

### Option B — Code Assistant Mode
Norma emits a spec bundle readable by an external code assistant (Claude Code, Copilot, Cursor).
The assistant reads the spec and builds the application.
Norma does not orchestrate the assistant — it only guarantees spec quality.

Both options are valid outputs of the same graph. The choice is a runtime parameter.

---

## 8. Repo Structure (Target)

```
norma/
  src/
    graph/
      intake.py            # COSTAR: requirement normalisation
      spec_advisor.py      # CRISPE: selects languages, generates runtime prompts
      spec_specialist.py   # Receives generated CRISPE, emits spec artefact
      constitutional.py    # CAI gate node (Promptfoo-backed)
      composer.py          # Assembles layered spec bundle
    pef/
      costar.py            # COSTAR framework builder
      crispe.py            # CRISPE framework builder
      persona.py           # PersonaLayer
      constitutional.py    # CAI output validator
    spec/
      languages.py         # Spec language registry (OpenAPI, AsyncAPI, Gherkin, …)
      bundle.py            # Layered spec bundle type
  evals/
    spec_quality.yaml      # Promptfoo: completeness, conformance, unambiguity
  docker/
    langfuse-compose.yml   # Self-hosted Langfuse
    litellm-config.yaml    # Virtual keys, routing, Ollama fallback
  .devcontainer/
    devcontainer.json
    Dockerfile
  pyproject.toml
  .env.example
```

---

## 9. Key Invariants

- **No ad-hoc prompts** — every prompt is assembled from named PEF components
- **Spec is the contract** — nothing downstream (build layer or code assistant) is authoritative over the spec
- **CAI gate is not optional** — every spec artefact passes the gate before emission
- **Observation is automatic** — Langfuse traces every node; Promptfoo runs evals on every artefact
- **Composable specs** — a single requirement can produce N artefacts in N languages; the bundle is the unit
- **Local-first inference** — cloud API is a fallback, not the default; Ollama handles validation passes

---

## 10. Not In Scope (at this stage)

- Persistent spec versioning / history store (deferred — address when spec volume justifies it)
- Dynamic meta-prompting as a designed feature (it emerges; do not engineer it prematurely)
- Fine-tuning local models on spec output (deferred)
- Multi-user / multi-tenant (single developer workflow for now)
