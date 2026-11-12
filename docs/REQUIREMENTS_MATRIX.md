# Requirements Matrix

| Requirement | Implementation location | Verification evidence | Status |
| --- | --- | --- | --- |
| R1 One marketplace port | `agent/marketplace_port.py`, simulator/memory/Upwork adapters | port, REST simulator, idempotency and graph integration tests | Complete; GigSim is the authoritative assignment marketplace and live Upwork is optional/not evaluated |
| R2 Three owned MCP servers | `mcp_servers/` | in-process protocol tests and reviewed full-schema hashes | Complete locally; manual Inspector captures pending |
| R3 Hand-written parallel graph | `agent/graphs/bid_graph.py` | parallel/skip/approval/budget tests and checkpoint timeline | Complete locally; instructor traces pending |
| R4 Approval before writes | graph interrupts, Postgres checkpointer and API approvals | exactly-once crash tests, history and read-only replay | Complete locally; Docker Postgres test also runs in CI |
| R5 Grounded claims | `rag/verify.py` | claim tests and synthetic normal/attack evaluation | Complete for synthetic study; human/instructor dev evaluation pending |
| R6 Measured retrieval | `rag/variants/`, synthetic RAG and ablation runners | 90-job V0/V1/V2/V3/V8 results plus dense/lexical/RRF ablation | Complete synthetic measurement and shipped choice; human relevance review pending |
| R7 Explicit memory promotion | `agent/memory/`, settings API/UI | promotion thresholds, durable store and deletion tests | Complete locally |
| R8 Tracing and budgets | `agent/observability.py`, `agent/telemetry.py`, Phoenix, graph runtime and run UI | trace propagation, OTLP tests plus local Phoenix 200/span-ingestion check, Prometheus/JSONL, baseline p95 | Complete locally; three public read-only trace URLs still require deployment |
| R9 Safety and platform respect | policy, redaction, bearer auth, rate limiting | injection, PII, auth, audit and synthetic attack tests | Complete locally; instructor attack set pending |
| R10 Deployable product | `infra/`, `apps/`, `render.yaml` | Compose validation, Render Blueprint tests, container smoke test and live URL | Render profile complete; live Blueprint application pending |
| A Tool-design study | `evals/datasets/tool_design_tasks.json`, `evals/runners/tool_design_eval.py` | 40 tasks × 3 designs in `evals/results/tool_design.json` | Complete locally; one-model limitation documented |
| A2 Open writer comparison | `evals/runners/model_profile_eval.py`, `agent/models.py` | 9 fixed jobs × Qwen3 4B/Llama 3.1 8B, raw rows and exact digests | Complete synthetic local comparison; Qwen selected, human preference pending |
| B RAG study | `evals/runners/`, `rag/variants/`, `evals/human_studies/` | 90-job metrics, component ablation, seeded attacks and reproducible human-study packets | In progress: author calibration labels and blind panel ratings remain human inputs |
| C Agent-design study | deterministic baseline plus `evals/runners/agent_model_design_eval.py` | 50-job public baseline and 36-row/two-model frozen GigSim result with raw plans, failures, tokens and outcomes | Complete locally; synthetic small-slice limitation documented |
| D Required UI | `apps/web/` | persisted onboarding, ranked inbox, private portfolio upload, evidence hover, paragraph regeneration, approvals and authenticated SSE | Complete locally; Render reviewer deployment pending |
| E Production engineering | `worker/`, `.github/`, `infra/`, `render.yaml`, `agent/observability.py`, `agent/telemetry.py` | durable Celery graph execution, scheduled deduplicated scouting, CI gates, Phoenix/OTLP traces, metrics, Compose and free Render profile | Complete locally; cost-safe Render deployment intentionally uses synchronous execution and deterministic models |
| X3 Portfolio Builder | `agent/nodes/portfolio_builder.py`, `evals/runners/portfolio_builder_eval.py` | 12-repository synthetic accuracy/safety study and approval conversion | Complete synthetic implementation; live official-GitHub validation needs user token |

The matrix is updated at the end of each phase. “Complete” requires both implementation and the
listed evidence; code alone is insufficient.

