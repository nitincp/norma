# Norma

Converts natural language requirements into layered, machine-readable spec bundles.

```
Requirement (natural language)
        ↓
  [ Norma ]
        ↓
Spec Bundle (OpenAPI · AsyncAPI · JSON Schema · Gherkin · MADR · C4 DSL)
        ↓
  ┌───────────────────────┐
  │ Option A — Build Layer │  Agents execute against the spec
  │ Option B — Code Assist │  Claude Code / Copilot reads spec, builds the app
  └───────────────────────┘
```

---

## Stack

| Tier | Role | Component |
|---|---|---|
| 3 | Orchestration | LangGraph (Python) |
| 2 | Routing / Gateway | LiteLLM |
| 1 | Observability | Langfuse (self-hosted) + Promptfoo (evals) |
| 0 | Inference | Ollama (local, CPU-only) + Anthropic / OpenAI via LiteLLM |

---

## Environment

**Host chain:** Windows (Hyper-V) → Linux VM (headless, CPU-only) → Docker DevContainer

VS Code connects to the Linux VM over SSH. The DevContainer runs inside Docker on the VM.
VS Code's SSH remote extension tunnels `forwardPorts` all the way through to Windows.

### Service URLs by context

Langfuse and LiteLLM run as Docker services on the **Linux VM host**, not inside the devcontainer.
Their ports are forwarded to Windows via the **"Norma SSH"** VS Code window (not the Dev Container window).

| Context | Langfuse | LiteLLM | Ollama |
|---|---|---|---|
| **Python code** (inside devcontainer) | `http://langfuse-web:3000` | `http://litellm-gateway:4000` | `http://host-gateway:11434` |
| **Linux VM shell** (outside Docker) | `http://localhost:3000` | `http://localhost:4000` | `http://localhost:11434` |
| **Browser** (Windows or VM, via VS Code SSH tunnel) | `http://localhost:3000` | `http://localhost:4000` | — |

> **Port forwarding source:** Use the **Norma SSH** VS Code window Ports panel to forward VM ports to Windows.
> The **Norma DevContainer** window only forwards ports from inside `app-runtime` — Langfuse and LiteLLM are not there.

> **Ollama** runs on the Windows host (via Hyper-V) and is reached from the devcontainer via `host-gateway`.
> It does not need a browser URL.

### Constraints

- CPU-only — no GPU/VRAM
- `OLLAMA_NUM_PARALLEL=1` is mandatory (prevents CPU thrashing)
- LiteLLM `request_timeout=30s`, `max_concurrent_requests=2`

---

## Graph

```
Requirement
     ↓
INTAKE NODE          — normalise + classify (COSTAR)
     ↓
SPEC ADVISOR NODE    — select spec languages; generate runtime prompts (CRISPE)
     ↓ (parallel per spec language)
SPEC SPECIALIST(s)   — emit spec artefact per language (generated CRISPE prompt)
     ↓
CONSTITUTIONAL AI GATE — validate: completeness, conformance, unambiguity (Promptfoo)
     ↓ proceed / revise → Specialist / reject → Advisor
COMPOSER NODE        — assemble layered spec bundle with cross-references
     ↓
Spec Bundle
```

---

## Repo Structure

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
      languages.py         # Spec language registry
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

## Setup

```bash
# 1. Open the repo in VS Code and reopen in Dev Container
# 2. Dependencies are installed automatically via postCreateCommand:
pip install -e '.[dev]'

# 3. Copy and fill environment variables
cp .env.example .env
```

---

## Key Invariants

- **No ad-hoc prompts** — every prompt is assembled from named PEF components (COSTAR, CRISPE, PersonaLayer, CAI gate)
- **Spec is the contract** — nothing downstream is authoritative over the spec
- **CAI gate is not optional** — every artefact passes the gate before emission
- **Observation is automatic** — Langfuse traces every node; Promptfoo evals every artefact
- **Local-first inference** — Ollama is the default; cloud API is a fallback
- **Composable specs** — one requirement → N artefacts in N spec languages; the bundle is the unit

---

## Spec Languages

| Layer | Language | Use |
|---|---|---|
| API contracts | OpenAPI 3.1 | REST surface, request/response schemas |
| Async / event | AsyncAPI 2.x | Event-driven surfaces, message schemas |
| Data shape | JSON Schema | Shared types, payload validation |
| Behaviour | Gherkin (`.feature`) | Given/When/Then acceptance criteria |
| Architecture decisions | MADR | Decisions that constrain implementation |
| System context | C4 DSL (Structurizr) | Component and container boundaries |

---

See [norma-requirements.md](norma-requirements.md) for the full requirements document.

See [backlog.md](docs/backlog.md) for requirements queued for pipeline processing.

See [execution-model.md](docs/execution-model.md) for how the project is built and iterated.

---

## Wins

### 2026-06-16 — Full stack connectivity verified, all 6 model endpoints healthy

**Langfuse v3.185.0** (self-hosted) and **LiteLLM gateway** both pass their full connectivity test suites (`scripts/test_langfuse.py`, `scripts/test_litellm.py`):

- Langfuse: health, auth, trace/span ingestion, score ingestion, dataset ops, prompt management, REST batch ingestion — all green.
- LiteLLM: all 6 model endpoints healthy with zero unhealthy endpoints.

| Model alias | Backend |
|---|---|
| `local/qwen2.5-0.5b` | `ollama/qwen2.5:0.5b` |
| `local/phi3-mini` | `ollama/phi3:mini` |
| `cloud/claude-sonnet` | `anthropic/claude-sonnet-4-6` |
| `cloud/gpt-4o` | `gpt-4o` |
| `cloud/gemini-flash` | `gemini/gemini-2.5-flash-lite` |
| `cloud/grok` | `xai/grok-3-mini` |

**Fix applied:** `gemini/gemini-2.0-flash-lite` was permanently retired by Google (HTTP 404). Migrated to `gemini/gemini-2.5-flash-lite`, which is the direct successor and confirmed working with the project API key. One-line change in `docker/litellm-config.yaml`.
