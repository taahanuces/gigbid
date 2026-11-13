# Phase Status

## Completed locally

- Phase 0: repository contracts, typed handoffs, policy/config boundaries, architecture decisions and
  deterministic smoke fixtures.
- Phase 1: complete bid vertical slice from job analysis through grounded proposal, approval interrupt
  and exactly-once draft creation; risky injected content terminates without a write.
- Phase 2 core: three MCP servers, v2 schemas and annotations, bearer verification, dry runs,
  idempotency, rate limiting, PII-masked audit logs, maintained LangChain client integration, official
  Upwork/GitHub connection boundaries and in-process protocol tests.
- Product slice: sign-in, inbox, job detail, run viewer, proposal editor, approval/edit/reject paths,
  checkpoint history/read-only replay, generated OpenAPI TypeScript contract, responsive layouts and
  degraded-mode banner.
- Production slice: per-request/graph trace correlation, a pinned self-hosted Phoenix OTLP viewer,
  content-free graph/model spans, Prometheus metrics, redacted JSONL spans and trace-viewer links,
  bounded graph budgets, late-ack Celery workers, atomic job enqueue,
  bounded PII-redacted dead letters, CI and a resolvable Compose stack.
- Experiment slice: synthetic three-persona portfolio/proposal corpus, five RAG variants, a 40-task
  local model tool-design comparison, a 50-job deterministic agent-control baseline and a frozen
  36-row/two-model hand-built/supervisor/ReAct study. Each report separates synthetic/public evidence
  from unavailable instructor or real outcome labels.
- Self-contained simulator slice: 300 public-data jobs, synthetic hidden client preferences,
  deterministic outcomes/faults, a REST adapter, an in-process adapter and a fixed 30-job-per-persona
  outcome study. Pipeline, Messages and Analytics now consume typed live APIs rather than placeholders.
- Product-control slice: onboarding/settings persist persona, rates, Connects limits and searches;
  tenant-scoped PDF/Markdown/text uploads are incrementally indexed and carried into durable runs;
  authenticated SSE updates the run timeline; paragraph regeneration, Critic metrics and citation hover
  are functional rather than decorative.
- Open-model/worker slice: a fixed two-model writer study selected Qwen3 4B over Llama 3.1 8B on
  validity, grounding, personalization and latency; routing supports Ollama/OpenAI-compatible endpoints,
  records writer tokens/latency, falls back to Llama and finally to the safe
  deterministic writer. Celery resumes durable start checkpoints and scheduled scouting deduplicates
  seen jobs before queueing them.
- RAG ablation/human-study slice: a 90-job dense/lexical/RRF ablation is committed, including the
  negative result that lexical-only beat type-diverse fusion. Reproducible blinded pairwise and
  calibration packets exist; no human results are fabricated.
- Submission-artifact slice: a visually verified nine-page PDF report, 1,594-word technical write-up,
  sixteen-class failure analysis, external-action checklist and production-build README GIF are
  generated. The Portfolio MCP image now packages and validates its 630-item synthetic demo corpus
  instead of starting with an empty index.
- Deployment slice: the tested Render Blueprint is live as a free Next.js reviewer service, a combined
  FastAPI + localhost-only GigSim service, and durable Postgres. Public health, reviewer login, the
  100-job inbox, a five-event/five-checkpoint hosted analysis, and a 390 by 844 mobile view were
  verified. The hosted profile uses GigSim, deterministic model execution and synchronous graph runs;
  the fuller Celery/Redis/Qdrant/open-model stack remains available and tested locally.

## Verified evidence

- Python unit, integration and contract suite passes.
- Ruff passes.
- TypeScript checking and the Next.js production build pass.
- Required Playwright flows pass on desktop and mobile viewports.
- Docker Compose resolves successfully from `.env.example`.
- `evals/results/smoke.json` is reproducible and explicitly labelled non-reportable synthetic smoke data.
- Three version-pinned Kaggle sources are downloaded and normalized locally with verified checksums,
  provenance labels, PII redaction and deterministic temporal/development splits.
- The 40-task tool-design study completed 120 local `llama3.1:8b` calls with zero runtime errors; raw
  predictions, exact scoring, model digest and latency/token results are committed.
- The 18-call final writer comparison completed on Qwen3 4B and Llama 3.1 8B with exact digests,
  raw outputs and host metadata; Qwen was selected by the registered validity/grounding rule.
- A public-data profile and category-specific pricing priors were derived from 1,292,791 real public
  contract rows; they are explicitly descriptive and preserve user/client constraints.
- A read-only 50-job architecture baseline compares hand-built, supervisor and ReAct-style control
  policies on identical public jobs; it reports control/safety metrics and explicitly withholds outcome
  claims because the policies are deterministic and GigSim labels are absent.
- A separate six-job × three-policy × two-model GigSim study preserves 36 raw controller rows. Final
  F1 and safety were 1.00/zero violations for every cell; Qwen controller completion was 0.833/1.000/
  0.833 for hand/supervisor/ReAct, while Llama completed all cells. Frozen retries, invalid Qwen
  outputs, tokens, latency and deterministic simulator outcomes are retained rather than hidden.
- Checkpoint history/replay, Phoenix/OTLP export, trace propagation/metrics, JSONL redaction, atomic worker enqueue and
  bounded dead-letter behavior have focused automated tests.
- Pinned Phoenix `20.12.0` booted locally, returned HTTP 200, accepted a content-free OTLP verification
  span, and exposed the resulting `gigbid` project through its read-only projects API.
- `make eval` regenerates the 90-job RAG study and the 90-run simulator outcome study; CI rejects
  regressions in bid F1, scam recall, reply rate, Recall@5 or claim verification.

## External inputs still required

The project now supplies its own simulator, persona corpora, authored development labels and outcome
engine. These support reproducible synthetic conclusions only; the project must not claim real-world
outcome causality. A genuine blind human panel and 30-item human judge calibration still require human
ratings. Live Upwork testing is not required because GigSim is the authoritative assignment
marketplace. Optional GitHub verification requires the user's PAT. The Render reviewer deployment is
complete, and its generated reviewer password remains only in Render and the student's handoff; no
credential is committed.
