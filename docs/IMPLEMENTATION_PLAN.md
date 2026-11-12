# Implementation Plan

The project is delivered in independently testable phases. A phase is complete only when its exit
checks pass and its evidence is committed.

## Phase 0 - Contracts and reproducibility

- Establish the required repository layout.
- Map assignment requirements to code, tests, traces, and result files.
- Define typed handoffs, safety invariants, configuration, and architecture decisions.
- Preserve a small deterministic data set for smoke tests.

Exit checks: unit tests for handoffs and configuration; no secrets; no inline prompts.

## Phase 1 - First vertical slice

- Read one GigSim-compatible job through the marketplace port.
- Run analyst, risk, and fit branches and combine their structured outputs.
- Retrieve evidence, decide bid/watch/skip, price, draft, verify, and check compliance.
- Stop at a durable approval payload; never send automatically.
- Show progress and the approval in the web application.

Exit checks: one deterministic job reaches approval with claim citations; one risky job is skipped.

## Phase 2 - MCP tool layer

- Complete Portfolio, Marketplace, and Workspace MCP servers.
- Add GigSim and Upwork adapters behind the marketplace port.
- Add tool schemas, annotations, authentication, rate limiting, retries, dry-run, idempotency, and
  append-only auditing.
- Add GitHub as the required third-party MCP server.

Exit checks: in-memory MCP tests, Inspector evidence, schema snapshots, degraded-mode recovery.

## Phase 3 - Advanced RAG

- Implement ingestion and incremental indexing.
- Implement V0, V1, V2, V3, and V8 as independently configurable variants.
- Add claim splitting, support classification, and corrective rewriting.
- Run retrieval, decision, proposal, outcome, cost, and latency evaluations.

Exit checks: `make eval` regenerates committed result files and the shipped variant is justified.

## Phase 4 - Durable LangGraph workflows

- Complete the bid and conversation graphs.
- Add Postgres checkpoints, approval interrupts, replay, budgets, bounded critique, failure states,
  and explicit memory promotion rules.
- Prove crash-and-resume and exactly-once marketplace writes.

Exit checks: all graph scenarios and durability tests pass.

## Phase 5 - Product interface

- Build all nine required screens and generate the API client from OpenAPI.
- Stream node events, preserve approvals across refreshes, and expose trace links.
- Add responsive, accessible interaction states and Playwright coverage.

Exit checks: five required end-to-end flows pass on desktop and mobile viewports.

## Phase 6 - Production engineering

- Add worker schedules, CI evaluation gates, tracing, PII masking, tenant isolation, token
  encryption, Docker images, and public deployment.
- Measure declared latency and cost budgets.

Exit checks: `docker compose up` works, smoke evaluation gates CI, reviewer login works publicly.

## Phase 7 - Research and extension

- Run the tool-granularity study on 40 tasks.
- Compare RAG variants and ablate the winning pipeline.
- Compare ReAct, supervisor, and hand-written graphs on the same 50 jobs.
- Build and evaluate X3 Portfolio Builder unless another extension is selected.

Exit checks: every reported number points to JSON or CSV under `evals/results/`.

## Phase 8 - Delivery and viva

- Finish README, report, demo, write-up, public traces, published Portfolio MCP, and resume bullet.
- Rehearse every failure and modification scenario listed in the assignment.

Exit checks: live URL, private reviewer login, on-time commit, reproducible evidence package.

