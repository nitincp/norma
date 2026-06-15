# The Software-to-GenAI Architecture Mapping

This comprehensive technical ledger acts as your core navigation compass, systematically translating your traditional enterprise microservices mental model into your new local, constraint-driven GenAI framework. [1]

## 1. System Infrastructure & Taxonomy Mapping

| Traditional Enterprise Layer (.NET Stack) [3, 4] | GenAI Structural Equivalent Layer | Architectural Purpose & Responsibility |
|---|---|---|
| YARP / API Gateway Proxy | LiteLLM Proxy (AI Gateway) | Standardizes all ingress/egress traffic. Exposes a unified OpenAI-spec endpoint. Abstracts provider-specific SDK payloads. |
| Azure Service Bus / RabbitMQ | LangGraph State Channels & Graph Events | Drives event-driven, multi-step asynchronous execution loops. Triggers state mutations and routing via event publications. |
| Redis Cache | LangGraph Local Checkpointers / Semantic Caches | Maintains short-term agent working memory and loop context across multi-turn iterations. Prevents redundant API token spend. |
| Azure Key Vault / Secrets | LiteLLM Virtual Keys | Enforces secure key rotation and tracking. Protects upstream provider keys (Anthropic, OpenAI) behind internal virtual tokens. |
| OpenTelemetry + App Insights | OpenLLMetry + Langfuse Engine | Provides deep distributed tracing. Tracks nested agent execution trees, tool call latencies, and generation outputs. |
| SQL Server / PostgreSQL | Vector Database (pgvector) + Metadata Storage | Holds semantic embeddings, persistent historical domain data, golden datasets, and long-term agent memory. |
| SOLID / Clean Architecture | Composite Prompt Architecture | Isolates prompt components (Persona, Task, Output Formatting) into single-responsibility, reusable code blocks assembled at runtime. |

------------------------------
## 2. The Local Inference & Hybrid Routing Layer

| Architectural Metric [5] | Cloud Provider Tiers (SaaS) | Local Tiny-Model Tier (On-Device Inference) |
|---|---|---|
| Primary Tooling | Claude 3.5 Sonnet / GPT-4o via API | Ollama / llama.cpp via local Docker Service |
| Model Size Target | Enterprise Frontier Models | 0.5B to 3B parameters (e.g., Qwen2.5-Coder-1.5B) |
| Hardware Execution | Multi-GPU Cloud clusters | Pure Local CPU execution (No GPU/VRAM dependence) |
| Storage Optimization | Managed by provider | Native mmap exploiting local 2.4 GB/s NVMe read speeds |
| Operational Role | Heavy reasoning, initial code generation, system architecture structuring. | Rapid syntax validation, lightweight tool calling, local compilation error scrubbing. |
| Gateway Routing Integration | Monitored by LiteLLM virtual tokens for cost metrics. | Configured via LiteLLM as an explicit fallback target or speed-optimized local router path. |

------------------------------
## 3. The Workspace & IDE Workspace Transformation## The IDE Paradigm Shift: Authoring Canvas vs. Supervisory Cockpit

Traditional IDE environments (like standard Visual Studio or bare-bones text editors) focus purely on an authoring loop where you manually type deterministic instructions. Your new workspace transitions into a Supervisory Control Cockpit: [6]

* The Code View: Shift from writing heavy infrastructure boilerplate to constructing high-level state machine boundaries (LangGraph graph configurations) and defining system specifications.
* The Prompt View: Prompts are separated entirely from the execution logic, treated as isolated code components, and managed as local code configuration files (.txt, .yaml).
* The Telemetry View: Breakpoints and step-through debuggers are replaced by Visual Trace Trees (Langfuse/Phoenix) rendered via port-forwarded browser tabs, allowing real-time oversight of multi-step autonomous loops.

## The Testing & Git Lifecycle Paradigm Shift

* Continuous Evaluation (Promptfoo): Replaces traditional unit testing frameworks (xUnit/Jest). Instead of testing if Input A exactly equals Output B, evaluations use semantic, non-deterministic assertions (LLM-as-a-judge) to check for logic drift, cost caps, and execution boundaries. [7, 8]
* Git Commit Strategy: Your version control history changes focus. Instead of recording variations of compiled business code logic, Git records the evolutionary lifecycle of System Archetypes, Guardrails, and Configuration-as-Code Prompts.

------------------------------
## 4. Headless Linux / DevContainer Topology
To protect the integrity of your host VM environment, the toolchain architecture divides responsibilities over a headless SSH loop:

[ WINDOWS CLIENT HOST ]
   └── VS Code UI (The Supervisory Cockpit view, Markdown editing, Terminal logs)
         └── Port Tunnels ──> localhost:3000 (Langfuse UI) & localhost:11434 (Ollama API)
                  │
        (Secure SSH Loop)
                  │
[ HEADLESS LINUX VM WORKSPACE ]
   └── Docker / DevContainer Lifecycle
         ├── app-runtime (Tier 3: Executes LangGraph state networks and runs local code tools)
         ├── litellm-gateway (Tier 2: Manages multi-provider keys, handles routing / failover targets)
         ├── langfuse-server (Tier 1: Embedded SQLite build mapping traces natively to NVMe disk)
         └── ollama-inference (Tier 0: Pinned to isolated CPU cores, running local quantized GGUF weights)

------------------------------
## Proceeding with the Redesign
This documentation map provides a structured blueprint of your architecture layers.
Now that you have your navigation ledger updated, would you like to focus on setting up the first actionable core—the LiteLLM configuration layer to link your cloud API keys with your local Ollama instance—or are you ready to test out your newly updated research prompt in a fresh Gemini session?

[1] [https://arxiv.org](https://arxiv.org/pdf/2512.05470)
[2] [https://bob.ibm.com](https://bob.ibm.com/blog/announcing-ibm-bob-launch)
[3] [https://engineeringideas.substack.com](https://engineeringideas.substack.com/p/the-personal-ai-platform-technical)
[4] [https://learn.microsoft.com](https://learn.microsoft.com/en-us/startups/build/ai/ai-app-architecture)
[5] [https://techcommunity.microsoft.com](https://techcommunity.microsoft.com/blog/microsoftmissioncriticalblog/azure-openai-architecture-the-decisions-that-actually-matter-part-1/4525976)
[6] [https://arxiv.org](https://arxiv.org/pdf/2503.02833)
[7] [https://www.mathworks.com](https://www.mathworks.com/videos/transforming-code-quality-and-v-v-in-modern-software-factories-using-polyspace-1741078564047.html)
[8] [https://dev.to](https://dev.to/kuldeep_paul/mastering-prompt-versioning-best-practices-for-scalable-llm-development-2mgm)
