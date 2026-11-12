# Submission Checklist

This checklist distinguishes repository-complete work from tasks that require the student, an
independent human, instructor-only data, live credentials, or a public account. Do not replace any
pending item with synthetic evidence.

## Repository implementation

- [x] Independent implementation; starter kit used only as a structural reference.
- [x] One `MarketplacePort` with in-memory, REST GigSim, and official-Upwork adapter boundaries.
- [x] Self-contained simulator with 300 public jobs and clearly labelled synthetic hidden state,
  conversations, proposals, faults, and outcomes.
- [x] Three owned MCP servers: Portfolio, Marketplace, and Workspace.
- [x] MCP authentication, strict schemas, annotations, rate limits, redacted audit logs, dry runs, and
  idempotent writes.
- [x] Parallel hand-written bid LangGraph and separate conversation LangGraph.
- [x] Durable Postgres checkpoints and explicit approval interrupt before every marketplace or
  workspace write.
- [x] RAG V0/V1/V2/V3/V8, post-generation claim verification, private upload indexing, and evidence
  hover details.
- [x] Open-model routing for measured Qwen3 4B primary, Llama 3.1 8B model fallback, and deterministic
  grounded fallback.
- [x] Next.js/FastAPI product: authentication, onboarding, ranked inbox, job detail, live run view,
  proposal editing, pipeline, messages, analytics, settings, and portfolio upload.
- [x] Celery long runs and scheduled saved searches with Redis deduplication and dead letters.
- [x] Prometheus metrics, trace correlation, redacted JSONL spans, self-hosted Phoenix/OTLP tracing,
  budgets, and cost metadata.
- [x] Docker Compose and CI configuration.
- [x] Pinned Phoenix service booted locally and accepted a content-free OTLP verification span.
- [x] X3 Portfolio Builder with explicit approval before private evidence creation.

## Reproducible evidence

- [x] Data source registry, license/provenance card, checksums, split rules, synthetic-field labels,
  limitations, and generated public profile.
- [x] 40-task × 3-design tool study with raw predictions and one-model limitation.
- [x] Nine-job-per-model Qwen3 4B vs Llama 3.1 8B writer study with raw outputs, exact digests,
  hardware, tokens, grounding, personalization, and latency.
- [x] 90-job × five-variant synthetic RAG study with negative hypothesis result retained.
- [x] Dense/lexical/type-diverse-hybrid ablation with the lexical-only ranking win retained.
- [x] 30 blinded proposal pairs and 30-item judge-calibration worksheet generated without scores.
- [x] 50-job deterministic control-policy baseline with outcome limitation retained.
- [x] Six-job × three-policy × two-model controller study with frozen budgets/failures, raw traces,
  tokens, latency, retries, safety fallback and explicitly synthetic GigSim outcomes.
- [x] 90-job fixed simulator outcome/safety study with synthetic rule-engine limitation retained.
- [x] 12-repository synthetic Portfolio Builder precision/recall/safety study.
- [x] Sixteen-class failure analysis with evidence and fixes.
- [x] Nine-page PDF engineering report, technical write-up, requirements matrix, runbook, and AI-usage
  disclosure.
- [x] Twenty Playwright cases across desktop and mobile.

## Final local verification

Run from the repository root in the configured Python environment:

```bash
ruff check --no-cache .
mypy agent apps mcp_servers rag worker data/pipelines evals
pytest -q
python -m evals.runners.check_regression
docker compose --env-file .env.example -f infra/docker-compose.yml config --quiet
cd apps/web && pnpm lint && pnpm build && pnpm test:e2e
```

- [x] Re-run the complete verification block on the current local submission state (12 November
  2026): Ruff, strict mypy, pytest, regression gate, Compose config, TypeScript, production build, and
  20 desktop/mobile Playwright cases passed.
- [x] Review generated evaluation JSON and confirm no local credential, private upload, hidden data, or
  `.env` file is staged.
- [ ] Tag the exact submission commit and record its SHA here: `____________________________`.

## Human evaluation — student/raters required

- [ ] The student labels all 30 judge-calibration items in the generated author worksheet.
- [ ] Run `make eval-judge-calibration`; record Cohen's kappa: `________`.
- [ ] If kappa is below the assignment threshold, revise the rubric/prompts before using judge scores.
- [ ] Recruit independent classmates/raters for the blinded V0/V2 proposal packet.
- [ ] Keep the separate answer key hidden until ratings are finalized.
- [ ] Aggregate preference, groundedness, personalization, and safety results; add them to the report
  without removing the current automatic metrics.

## Model and agent comparison

- [x] Pull and pin the two writer models; record exact names/digests and Apple M4 hardware.
- [x] Run both writer profiles on the same frozen nine-job synthetic slice, seed, prompt, retriever,
  personas and budgets; preserve raw rows in `evals/results/model_profiles.json`.
- [x] Freeze the same simulator job set, seed, personas, budgets, and failure schedule for the agent
  architecture comparison.
- [x] Execute the hand-built, supervisor-style, and ReAct-style policies with real model calls.
- [x] Report completion, safety, outcome, token, cost, latency, retry, and failure metrics separately.
- [x] Preserve raw traces and explicitly distinguish the prior deterministic control baseline.

## Optional live integrations — not required for the GigSim submission

- [x] Use the self-contained GigSim as the authoritative assignment marketplace and clearly label its
  conversations, proposals, hidden state and outcomes as synthetic.
- [x] Keep the official Upwork MCP adapter disabled in the deployment; no Upwork account, credential or
  live write is required for this submission.
- [ ] Supply `GITHUB_TOKEN` locally and validate the X3 builder on consented repositories.
- [ ] Record token scopes, revoke temporary credentials after testing, and document live-test limits.

## Deployment and public evidence — Render account required

- [x] Define a cost-safe Render Blueprint with two free web services and free Postgres.
- [x] Configure the deployed reviewer profile for GigSim, deterministic model execution, synchronous
  graph runs, generated application secrets, exact CORS origin, TLS and health checks.
- [ ] Apply the Blueprint from the final GitHub repository and wait for all three resources to be live.
- [ ] Create and verify the reviewer account with only synthetic demonstration data.
- [ ] Public application URL: `________________________________________________`.
- [ ] Reviewer login/instructions: `____________________________________________`.
- [x] Configure local Phoenix OTLP tracing with PII redaction and content-free graph/model spans.
- [ ] Deploy the trace viewer securely and publish three read-only trace URLs:
  `________________`, `________________`, `________________`.
- [ ] Verify the public app from a clean browser and mobile viewport.
- [ ] Add deployed URLs to the README and PDF/report source, then rebuild the PDF.

## Presentation and publication — student required

- [ ] Record a demonstration of no more than three minutes: onboarding → ranked job → run timeline →
  cited proposal → paragraph revision → approval → pipeline/messages/analytics.
- [ ] Include one failure/safety example and make clear when GigBid is using synthetic data.
- [ ] Video URL: `___________________________________________________________`.
- [x] Capture a short README GIF from the production UI build with clearly synthetic fixtures and add
  it under `docs/assets/`.
- [ ] Optionally recapture the GIF against the final public deployment if its UI differs materially.
- [ ] Publish the Portfolio MCP server/package through the instructor-approved channel and record its
  install URL/version: `____________________________________________________`.
- [ ] Publish the 1,200–1,800 word technical write-up and record the URL:
  `________________________________________________________________________`.
- [ ] Put the two-line resume bullet from `docs/TECHNICAL_WRITEUP.md` into the requested submission
  field.

## Instructor-only completion

- [ ] Insert the exact final change-request text supplied by the instructor.
- [ ] Implement the change without altering the frozen baseline results.
- [ ] Record changed files/lines, elapsed time, new tests, and before/after behavior.
- [ ] Run the instructor hidden job and adversarial sets; report them separately from authored tests.
- [ ] Complete the required oral defense or live review.

## Final package review

- [x] PDF remains at most ten report pages; appendices, if permitted, are clearly separated.
- [ ] All links resolve without editor/session access.
- [x] Every result says whether its data is public, synthetic, human-rated, live, or instructor-hidden.
- [x] No unperformed human, optional live-platform, deployment, or hidden-test result is claimed.
- [ ] Repository visibility, release tag, report, video, app, traces, write-up, and MCP publication match
  the submission form exactly.
