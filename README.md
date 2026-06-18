# Norma

**PEF-compliant requirement processor.**

Takes a natural language requirement. Runs it through composable Prompt Engineering Framework (PEF) nodes. Emits a spec bundle — machine-readable, human-validatable, industry-standard. The spec feeds a code assistant, which builds the app. The built app is the validation of the spec.

See [docs/vision.md](docs/vision.md) for the full picture.

---

## Stack

| Tier | Role | Component |
|---|---|---|
| 3 | Orchestration | LangGraph (Python) |
| 2 | Routing / Gateway | LiteLLM |
| 1 | Observability | Langfuse (self-hosted) |
| 0 | Inference | Cloud providers via LiteLLM |

All inference goes through LiteLLM — Norma never calls providers directly.

---

## Setup

```bash
./scripts/bootstrap.sh   # uv-managed Python 3.12, sync deps, connectivity check
cp .env.example .env     # fill in API keys
```

Services (Docker on Linux VM host):

| Service | URL |
|---|---|
| Langfuse | `http://localhost:3000` |
| LiteLLM | `http://localhost:4000` |

---

## Docs

| Doc | Purpose |
|---|---|
| [docs/vision.md](docs/vision.md) | What Norma is, the spec contract, the validation loop, invariants |
| [docs/PROCESS.md](docs/PROCESS.md) | How we build — iteration rhythm, PEF refinement, expansion triggers |
| [docs/backlog.md](docs/backlog.md) | Requirements queued for the pipeline |
| [docs/findings.md](docs/findings.md) | Run observations and trace analysis |
