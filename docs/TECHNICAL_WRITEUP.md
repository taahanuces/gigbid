# Building GigBid: a grounded, human-controlled freelancer copilot

Freelance marketplaces create a deceptively difficult agent problem. Finding a job is easy; deciding
whether it is safe and worth the limited proposal budget, locating evidence that truly supports the
pitch, pricing the work, and communicating without violating platform policy are not. GigBid is an
independent implementation of a multi-agent copilot for that workflow. It discovers jobs, evaluates
risk and fit, retrieves private portfolio evidence, drafts a cited proposal, and stops at an explicit
human approval boundary before any marketplace write. The project is intentionally more than a chat
demo: it includes three owned MCP servers, durable LangGraph workflows, a self-contained marketplace
simulator, a responsive web product, asynchronous workers, and reproducible evaluation harnesses.

## Architecture and control flow

The system separates reasoning from effects. A Next.js client talks to a typed FastAPI boundary.
FastAPI authenticates the tenant and user, validates the request, seeds a durable LangGraph checkpoint,
and either executes synchronously or sends a thread identifier to Celery. Workers resume the same
thread from Postgres, so a process restart does not silently lose an approval or repeat an action.
Redis provides the queue and deduplication support; Qdrant is available for vector storage; Ollama
serves the configured open models. Authenticated server-sent events expose checkpoint changes to the
run timeline without placing graph execution inside a browser request.

The bid graph begins with a marketplace load and then fans out into Job Analyst, Risk Assessor, and Fit
Matcher nodes. Their typed reports meet at a deterministic decision join. A skip terminates without an
effect; an uncertain job becomes a needs-attention item; a bid continues through pricing, portfolio
retrieval, writing, claim verification, a bounded Critic loop, compliance, and approval. The separate
conversation graph classifies client messages, prepares a cited answer or tentative scheduling option,
and uses the same approval rule. Graph state contains only the current typed hand-offs. Execution
history lives in checkpoints and traces, while longer-term preferences or outcomes enter memory only
after explicit promotion thresholds. This prevents a model from treating its own transient output as
trusted memory.

## MCP as the effect boundary

GigBid owns Portfolio, Marketplace, and Workspace MCP servers. Portfolio exposes verified evidence,
case studies, skills, and read-only resources. Marketplace exposes job and client reads plus proposal
and message writes. Workspace exposes availability and tentative draft operations. Inputs are strict
Pydantic schemas, read/write intent is annotated, and every endpoint is protected by bearer
authentication, rate limits, tenant metadata, and redacted audit records. Marketplace writes also
require a dry-run approval payload and an idempotency key. The official Upwork and GitHub MCP services
exist only behind adapters, so the graph cannot scrape a site or acquire ambient browser authority.

Tool design was measured rather than chosen by intuition. Forty known-call tasks were run through
fine-grained, coarse, and description-rewritten designs with the same local `llama3.1:8b` model. The
fine-grained design achieved 1.00 tool selection and 0.60 exact argument accuracy, compared with 0.80
and 0.15 for the coarse design. More verbose descriptions restored selection to 1.00 but argument
accuracy was 0.50 and token use increased. The shipped surface therefore uses small single-purpose
tools and strict server validation. The result is limited to one local model, but it supplies a
defensible engineering decision and preserves the raw predictions for inspection.

## Retrieval, grounding, and negative results

The retrieval corpus contains explicitly synthetic portfolios and past proposals for three personas;
it is separate from the public Kaggle job and contract records. Each portfolio item has a stable
evidence identifier, skills, technology tags, source metadata, and a text body. A 90-job authored
benchmark supplies ten relevant evidence items per job. This makes Recall@5 intentionally capped at
0.5 and prevents a misleading perfect score. Five variants were compared: dense V0, requirement
decomposition V1, hybrid V2, reranked V3, and corrective V8.

The preregistered hypothesis failed. V1 and V8 reduced Recall@5 from 0.494 to 0.378 because broad,
repeated requirements diluted distinctive evidence. Type-diverse V2 reached 0.500 Recall@5, 1.000 MRR
and 0.801 nDCG@10; V3 reached 0.498, 1.000 and 0.749. A component ablation was also negative:
lexical-only retrieval beat hybrid fusion on nDCG, 0.833 versus 0.801. V2 still ships because it
reaches maximum Recall@5, retains semantic recall for paraphrases, and prevents past proposals from
crowding case studies, code and reviews out of the writer context. This is a grounding/robustness
choice, not a claim that fusion won the benchmark.

Grounding is enforced after generation. The writer must attach evidence IDs to material claims, but the
verifier also discovers experience and outcome claims directly from the prose so a model cannot evade
verification by omitting metadata. Unsupported or over-broad claims are removed or narrowed before the
Critic sees the proposal. In the seeded attack set, one unsupported claim survived before verification
and zero after it. Citation hover cards in the proposal studio expose the supporting evidence to the
reviewer. Private PDF, Markdown, and text uploads are tenant-scoped, size-limited, incrementally
indexed, and excluded from version control.

## Product and production behavior

The application includes authentication, persisted onboarding, a ranked inbox, job detail, live run
viewer, proposal studio, pipeline, messages, analytics, and settings. A user selects a persona, hourly
and fixed-price floors, weekly and per-job Connects limits, and saved searches. Those settings feed the
actual graph: they influence retrieval, pricing, bid gates, and scheduled scouting. Proposal paragraphs
can be regenerated individually, but the result returns through claim verification and compliance.
Approval can accept, edit, or reject the pending payload; replay is read-only.

Long jobs run through Celery with late acknowledgement, bounded retries, dead-letter storage, and a
model fallback followed by a deterministic grounded fallback. A fixed nine-job-per-model synthetic
writer study selected Qwen3 4B over Llama 3.1 8B: both had 1.00 JSON validity, citation precision,
grounding and Critic pass rate, while Qwen reached 0.630 personalization and 11.4-second p95 versus
0.556 and 33.5 seconds. Qwen is primary and Llama is the model fallback through a shared
Ollama/OpenAI-compatible interface. Each call records model, tokens, latency, local cost and fallback.

A second frozen study used both models to control hand-built, supervisor-style and ReAct-style plans
over six GigSim scenarios with identical evidence, budgets and injected retry schedules. Every final
decision matched the authored bid/skip label and no attack reached a bid, but controller reliability
and cost differed. Llama completed all 18 controller rows. Qwen completed 5/6 hand-built, 6/6
supervisor and 5/6 ReAct rows; on the two failures it echoed the untrusted observation instead of the
required action schema. The bounded deterministic fallback preserved the correct safe result. ReAct
also consumed the most output tokens and had the highest p95 latency for both models. This supports
keeping orchestration deterministic; model planning added no synthetic outcome benefit.

Trace identifiers flow from HTTP to graph state and marketplace audit events.
Prometheus metrics and redacted JSONL spans work locally. A pinned self-hosted Phoenix service receives
content-free OTLP spans for HTTP, graph and model operations; prompts and portfolio/proposal bodies are
excluded from span attributes. Public read-only trace links still require secured deployment.

The local product is packaged with Docker Compose: web, API, worker, beat, three MCP servers,
simulator, Postgres, Redis, Qdrant, Ollama, and Phoenix. Tests cover Python units and integrations, MCP
contracts, tenant isolation, exactly-once writes, restart/resume behavior, prompt injection, claim
verification, and responsive browser flows. Twenty Playwright cases pass across desktop and mobile.
CI runs static typing, linting, tests, production web build, Compose validation, evaluations, and
regression thresholds.

The public reviewer profile is deployed at `https://gigbid-web.onrender.com`. Render runs the Next.js
UI, a combined FastAPI and localhost-only GigSim service, and durable Postgres. A clean login loaded
100 simulated jobs; a hosted analysis completed five graph events and five checkpoints, and its run
view was verified at desktop and 390 by 844 mobile sizes. The free profile uses deterministic models
and synchronous execution to avoid pretending that GPU, Redis or Celery capacity exists in the hosted
demo; the fuller production topology is the locally tested profile described above.

## Data, simulator, and extension

The simulator uses 300 Apache-2.0 public Kaggle job records, then adds clearly labelled synthetic
client preferences, conversations, proposals, hidden outcome labels, and fault schedules. Public
contract records contribute descriptive category pricing priors; they are not treated as causal
evidence. A fixed 90-job simulator study measured bid/skip F1 and scam recall of 1.00 for each persona,
with reply rates between 0.667 and 0.917 and hire rates between 0.542 and 0.667. Those rates describe a
deterministic synthetic rule engine, not expected Upwork performance. Source URLs, licenses, hashes,
transforms, split rules, limitations, and synthetic fields are documented in the data card.

The signature X3 Portfolio Builder reads repositories through allowlisted official GitHub MCP tools,
detects code-backed technologies, quarantines unsupported README outcome claims, and creates a pending
case-study candidate. Only approval converts the verifiable subset into private portfolio evidence.
On 12 authored synthetic repository snapshots it achieved 1.00 technology precision and recall, 1.00
recall for planted unsupported claims, and zero false positives. Live GitHub validation still requires
the student's token and must be reported separately.

## Lessons and honest completion boundary

The most important lesson is that model quality and system safety solve different problems. Better
prompts would not have fixed nullable public budgets, a hard-coded UI price floor, a duplicate write,
or a lost approval checkpoint. Typed contracts, deterministic joins, policy checks, idempotency,
post-generation verification, and tenant boundaries caught those failures. The negative RAG results
were also useful: they prevented a more complicated retriever from being presented as an automatic
improvement.

The local implementation and synthetic/public-data evidence are reproducible. Several submission
items cannot be honestly manufactured by code: 30 human calibration labels and Cohen's kappa, a blind
classmate panel, optional GitHub PAT validation, instructor hidden-test results, external read-only trace
URLs, a recorded demonstration, and the instructor's exact final change-request text. The repository
provides worksheets, commands, placeholders, and a checklist for those tasks. They should be completed
with genuine people, credentials, and deployment evidence before final submission.

**Resume bullet:** Built GigBid, a durable LangGraph/MCP freelancer copilot with grounded RAG,
human-gated marketplace writes, open-model routing, and a responsive Next.js/FastAPI product. Designed
reproducible tool, retrieval, simulator, and safety evaluations over public and explicitly synthetic
data, with CI regression gates and failure-aware production controls.
