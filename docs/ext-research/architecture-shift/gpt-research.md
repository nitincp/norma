# FULL-STACK COMPATIBILITY VERDICT

**PASS (with restrictions): The most compatible architecture under a headless Linux VM, CPU-only inference, VS Code SSH workflow, and ~2.4 GB/s NVMe storage is currently: LangGraph → LiteLLM → Langfuse (+ Promptfoo) → Ollama. Most alternative stacks fail not because of missing features, but because they introduce excess runtime overhead, excessive background services, memory amplification, or observability complexity that provides little value when Tier 0 inference is already the dominant bottleneck.**

The critical observation is that **CPU-bound inference changes the optimization hierarchy**. In GPU-centric deployments, orchestration and observability overhead are relatively insignificant. In your environment, however, Tier 3 and Tier 1 can easily consume enough CPU cycles to materially reduce inference throughput.

---

# Unified Cross-Tier Comparison Matrix

| Stack Combination                                     | CPU Overhead | RAM Footprint | NVMe Utilization | Operational Complexity | Trace Quality | Agent Reliability | Constraint Fit |
| ----------------------------------------------------- | ------------ | ------------- | ---------------- | ---------------------- | ------------- | ----------------- | -------------- |
| LangGraph + LiteLLM + Langfuse + Ollama               | Low          | Moderate      | Excellent        | Moderate               | Excellent     | High              | PASS           |
| LangGraph + LiteLLM + Phoenix + Ollama                | Very Low     | Low           | Good             | Low                    | Good          | High              | PASS           |
| AutoGen + LiteLLM + Langfuse + Ollama                 | Moderate     | Moderate      | Good             | Moderate               | Moderate      | Moderate          | CONDITIONAL    |
| CrewAI + LiteLLM + Langfuse + Ollama                  | Moderate     | Moderate      | Good             | Low                    | Moderate      | Moderate          | CONDITIONAL    |
| AutoGen + Phoenix + Ollama                            | Moderate     | Low           | Good             | Low                    | Limited       | Moderate          | CONDITIONAL    |
| LangGraph + OpenTelemetry-only + Ollama               | Lowest       | Lowest        | Excellent        | High Manual Work       | Limited       | High              | CONDITIONAL    |
| Multi-Agent AutoGen + Langfuse + Local Models         | High         | High          | Poor             | High                   | Good          | Low               | FAIL           |
| CrewAI + Multiple Local Agents + Vector Memory Layers | Very High    | High          | Poor             | High                   | Moderate      | Low               | FAIL           |

---

# Tier 3 — Orchestration Layer

The orchestration layer becomes the second most important performance component after inference.

| Framework         | CPU Cost | State Persistence | Recovery  | Trace Mapping | Headless Fit |
| ----------------- | -------- | ----------------- | --------- | ------------- | ------------ |
| LangGraph         | Low      | Excellent         | Excellent | Excellent     | PASS         |
| AutoGen           | Moderate | Weak              | Moderate  | Moderate      | CONDITIONAL  |
| CrewAI            | Moderate | Weak              | Moderate  | Limited       | CONDITIONAL  |
| OpenAI Agents SDK | Low      | Good              | Good      | Good          | CONDITIONAL  |

### Why LangGraph Wins

Your environment is fundamentally a long-running workflow environment.

The major advantage is not agents.

The major advantage is:

* deterministic state transitions
* checkpointing
* resumability
* explicit graph execution

These align directly with enterprise service orchestration patterns.

A LangGraph checkpoint can be mapped almost 1:1 into a trace tree within Langfuse.

This creates a clean architecture:

```text
Graph Node
   ↓
Span
   ↓
Trace
   ↓
Evaluation
```

Most alternatives lack this direct structural correspondence.

---

# Tier 2 — Routing & Gateway Layer

CPU-only environments expose weaknesses in routing systems.

The gateway must absorb:

```text
Agent Burst
        ↓
Request Queue
        ↓
Local CPU Saturation
        ↓
Inference Wait
```

rather than merely forwarding requests.

| Gateway            | Queue Behavior | Provider Abstraction | Local Model Support | Resource Cost    | Fit         |
| ------------------ | -------------- | -------------------- | ------------------- | ---------------- | ----------- |
| LiteLLM            | Excellent      | Excellent            | Excellent           | Low              | PASS        |
| OpenRouter Gateway | Cloud-oriented | Excellent            | Weak                | Low              | FAIL        |
| Custom Gateway     | Variable       | Variable             | Excellent           | High Maintenance | CONDITIONAL |
| Portkey            | Good           | Excellent            | Moderate            | Moderate         | CONDITIONAL |

### Why LiteLLM Dominates

The architecture requires:

```text
Tier 3
   ↓
Tier 2
   ↓
Ollama
```

without forcing orchestration code to know model endpoints.

LiteLLM provides:

* model abstraction
* fallback routing
* retry logic
* request normalization

with very small runtime cost.

This is exactly what a CPU-bound stack needs.

---

# Tier 1 — Observability & Evaluation

This is where most stacks accidentally become bloated.

The goal is not maximum telemetry.

The goal is sufficient telemetry.

| Platform           | Runtime Cost  | Storage Cost | Evaluation Support | Agent Visibility | Fit         |
| ------------------ | ------------- | ------------ | ------------------ | ---------------- | ----------- |
| Langfuse           | Moderate      | Moderate     | Excellent          | Excellent        | PASS        |
| Phoenix            | Low           | Low          | Good               | Good             | PASS        |
| Promptfoo          | Near Zero     | Near Zero    | Excellent          | None             | PASS        |
| OpenTelemetry Only | Lowest        | Lowest       | Weak               | Weak             | CONDITIONAL |
| Helicone           | Cloud-centric | Moderate     | Moderate           | Moderate         | FAIL        |

### Recommended Structure

Production:

```text
Langfuse
+
Promptfoo
```

Development:

```text
Phoenix
+
Promptfoo
```

Reason:

Promptfoo consumes almost no runtime resources because evaluation runs outside the critical inference path.

---

# Tier 0 — Local Inference Layer

This layer determines everything else.

Every architectural decision should assume:

```text
CPU = bottleneck
```

not storage.

Not networking.

Not orchestration.

CPU.

---

## Ollama Assessment

| Metric                 | Result    |
| ---------------------- | --------- |
| Headless Support       | Excellent |
| VS Code Integration    | Excellent |
| CPU Inference          | Good      |
| Model Management       | Excellent |
| Resource Overhead      | Low       |
| Operational Complexity | Very Low  |

### Hidden Advantage

The 2.4 GB/s NVMe largely eliminates model-loading concerns.

Typical 1B–3B models:

| Model Size | Load Time |
| ---------- | --------- |
| 1 GB       | <1 sec    |
| 2 GB       | ~1 sec    |
| 4 GB       | ~2 sec    |

Inference remains dramatically slower than storage.

Therefore:

**Inference latency dominates architecture.**

Not model loading.

Not checkpoint persistence.

Not trace writing.

---

# Cross-Layer Friction Log

## Friction #1

LangGraph without Langfuse

Result:

```text
Graph checkpoints
exist

Trace visibility
doesn't
```

You lose the strongest debugging capability.

---

## Friction #2

AutoGen with Local CPU Models

Result:

```text
More agent conversations
=
More inference calls
=
CPU collapse
```

Multi-agent architectures become disproportionately expensive.

---

## Friction #3

Heavy Vector Databases

Many developers add:

* Qdrant
* Weaviate
* Milvus

immediately.

For 0.5B–3B local models this is often architectural overkill.

A simple:

```text
SQLite
+
FTS5
```

or

```text
DuckDB
```

frequently outperforms the operational burden.

---

## Friction #4

Langfuse + Excessive Span Logging

The NVMe is fast enough.

The CPU isn't.

If every token event becomes a trace event:

```text
CPU
becomes
telemetry-bound
```

before storage-bound.

---

# Storage Architecture Assessment

Your storage subsystem is unusually strong relative to the compute layer.

| Component               | Bottleneck? |
| ----------------------- | ----------- |
| NVMe Reads              | No          |
| NVMe Writes             | No          |
| SQLite Checkpoints      | No          |
| LangGraph State Storage | No          |
| Trace Persistence       | No          |
| Ollama Model Loading    | No          |
| CPU Inference           | Yes         |

Therefore the architecture should exploit storage aggressively:

* persistent checkpoints
* local trace retention
* evaluation datasets
* conversation replay
* prompt versioning

while minimizing anything that creates additional inference requests.

---

# Recommended Enterprise-Minimal Stack

| Tier             | Selection            |
| ---------------- | -------------------- |
| Tier 3           | LangGraph            |
| Tier 2           | LiteLLM              |
| Tier 1           | Langfuse + Promptfoo |
| Tier 0           | Ollama               |
| State Store      | SQLite initially     |
| Evaluation Store | DuckDB               |
| Vector Layer     | None initially       |

This is currently the highest signal-to-overhead architecture that satisfies the stated constraints.

---

### Cross-Layer Challenge Question

If a LangGraph workflow can spawn parallel branches while Ollama is already saturating all CPU cores with a single 3B model inference, **what is the queue-control strategy in Tier 2: backpressure into the graph executor, request batching at LiteLLM, or graph-level concurrency limits—and which layer should own that decision to avoid hidden latency amplification across the entire stack?**
