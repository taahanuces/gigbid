# Failure Analysis

GigBid records failures by system boundary rather than hiding them behind aggregate scores. The table
below is the report-level taxonomy; the notes that follow preserve the evidence, root cause, repair,
and remaining limitation for each class. Unless marked public, the examples come from authored
synthetic fixtures or local fault injection.

| # | Failure class | Observed example | Root cause | Repair / current status |
| --- | --- | --- | --- | --- |
| 1 | Missed evidence | V1 Recall@5 fell from 0.494 to 0.378 | Broad repeated requirements diluted distinctive terms | Keep V2; retain negative result and per-query diagnostics |
| 2 | Retrieval fusion | Lexical nDCG 0.833 vs hybrid 0.801 | Fusion/type diversity trades ranking for evidence coverage | Ship V2 for maximum Recall@5, paraphrases and claim-support diversity |
| 3 | Wrong skip | Sparse synthetic portfolios caused 45/50 baseline skips | Fit policy correctly saw no support, but benchmark did not cover personas | Show evidence gaps; require review; do not call skips true errors |
| 4 | Mispricing | Public jobs sometimes had only a single or null budget bound | Initial schema assumed a complete min/max interval | Nullable schema; user floor and explicit client constraints take precedence |
| 5 | Unsupported claim | Draft contained a planted “300% improvement” guarantee | Model-supplied claim metadata could omit material prose claims | Discover claims from prose; remove/narrow unsupported text |
| 6 | Generic opening | Synthetic client preference penalized boilerplate | Writer did not use job/client details strongly enough | Personalization metric plus paragraph-level rewrite and re-verification |
| 7 | Compliance miss | Job content included off-platform contact instructions | Marketplace content is untrusted and initially reached the draft | Policy pack, delimiters, sanitizer, blocking reason, zero-write route |
| 8 | Prompt injection | Job told the agent to ignore rules and reveal data | Untrusted content was semantically imperative | Explicit trust boundary, injection flag, no tool authority, attention route |
| 9 | Tool argument error | Fine-grained design had only 0.60 exact argument accuracy | Correct selection did not guarantee schema-complete arguments | Strict Pydantic validation and safe error return; never trust selection alone |
| 10 | Marketplace outage | Injected 429/5xx interrupted a write path | Remote services are unavailable and retries can duplicate effects | Backoff, deadline, idempotency key, late acknowledgement and DLQ |
| 11 | Model unavailable | Ollama endpoint or configured model was missing | Local model lifecycle is outside graph control | Configured small-model retry, then deterministic grounded fallback |
| 12 | UI policy drift | Frontend displayed a hard-coded USD 300 price floor | Presentation duplicated domain policy | Persisted profile is the single source; API and browser regression tests |
| 13 | Duplicate scheduled work | Beat could rediscover an already queued saved-search job | Discovery and enqueue were separate non-atomic decisions | Durable seen-job key and enqueue deduplication |
| 14 | Lost approval state | A restarted API could forget a pending draft | In-memory execution coupled approval to one process | Postgres START/checkpoint persistence and resume-by-thread tests |
| 15 | Reasoning runaway | Qwen3 spent minutes on a compact JSON writer call | Thinking mode was unnecessary and output was unbounded | Disable optional thinking, cap output, enforce explicit word limits |
| 16 | Citation contract miss | Models paraphrased IDs or used placeholders/Markdown links | Natural-language “cite evidence” instruction was underspecified | Require exact plain bracket IDs; expand prose claim discovery |

## 1. Missed evidence after requirement decomposition

The V1 retriever decomposed a job into several requirements and issued one query per requirement. The
hypothesis was that decomposition would improve coverage. It did the opposite: Recall@5 fell from
0.494 for V0 to 0.378, and MRR fell from 0.989 to 0.664. Inspection showed that broad requirements such
as communication and testing appeared repeatedly and pushed distinctive evidence down the list. The
repair was not to hide or tune away the result. V2 keeps hybrid retrieval with deduplicated candidates,
and the report states that the preregistered hypothesis failed. Query-level results are preserved in
`evals/results/synthetic_rag.json`.

## 2. Fusion did not win the ablation

On the dense/lexical/RRF ablation, lexical-only retrieval achieved 0.833 nDCG@10 while the shipped
type-diverse hybrid achieved 0.801. The direction contradicts the expected fusion benefit. V2 remains
the default because it reaches maximum Recall@5, retains a semantic path for paraphrases, and prevents
the much larger past-proposal pool from excluding case studies, code and reviews. Documentation
describes this as a grounding/coverage trade-off rather than a ranking win. A human relevance panel
remains necessary to decide whether semantic matches are genuinely more useful.

## 3. Apparent wrong skips in the control-policy baseline

Forty-five of fifty public jobs were skipped when paired with sparse synthetic portfolios. These are
not labelled real-world errors: the control policies shared the same analysis nodes and correctly
found inadequate evidence according to their inputs. The benchmark exposed a coverage mismatch rather
than proving a bad controller. The UI now surfaces missing-evidence reasons and offers a needs-attention
route. The later frozen two-model simulator comparison preserved this baseline and found no final
decision or rule-engine outcome gain from model-planned supervisor/ReAct variants.

## 4. Nullable and open-ended budgets

One public-data preprocessing path assumed that both minimum and maximum budgets existed. Real
postings can provide one bound, an hourly range, a fixed value, or no numeric budget. This caused a
validation failure and could have produced misleading prices. The budget model now accepts nullable
bounds, and the pricing precedence is explicit: client constraints, then user floor, then descriptive
public priors. Tests cover the incomplete-budget records that revealed the defect.

## 5. Unsupported material claims

A seeded draft included a strong outcome claim while omitting the claim from its structured metadata.
A verifier that trusted only writer-provided metadata would have missed it. The verifier now discovers
experience, guarantee, percentage, and outcome claims directly from final prose, resolves cited
evidence IDs, and removes or narrows anything unsupported. The attack evaluation records one material
unsupported claim before verification and zero afterward. This is a constrained authored attack set,
not a universal factuality guarantee.

## 6. Generic proposal language

The simulator's client preferences penalize generic openings, revealing that a grammatically valid
proposal can still be ineffective. The Critic records a personalization score, and the proposal studio
can regenerate one selected paragraph with job and evidence context. Crucially, regenerated text is
sent back through claim verification and compliance rather than patched directly into an approved
payload. Real client preference still needs human evaluation.

## 7–8. Compliance and prompt injection

Authored jobs and messages contain off-platform contact requests, secret-exfiltration instructions,
and “ignore previous rules” attacks. Treating marketplace text as instructions would collapse the
trust boundary. Inputs are delimited as untrusted data, injection and scam signals enter the typed risk
report, policies block prohibited content, and affected runs terminate or request attention before any
write tool is available. Tests assert zero marketplace effects on these paths. Instructor-only attacks
remain a separate future evaluation.

## 9. Correct tool, wrong arguments

The fine-grained MCP design achieved perfect tool selection but only 0.60 exact argument accuracy in
the 40-task local-model study. This makes an important distinction: semantic selection is not input
correctness. Every tool therefore validates length, range, enum, tenant, authorization, and approval
fields at the server. Invalid requests return typed errors without an effect. The current study uses
one model and should be repeated with the assignment's comparison model before broad conclusions.

## 10–11. External service and model failures

Fault schedules inject timeouts, 429 responses, and 5xx failures. Marketplace writes use stable
idempotency keys so a retry cannot create a second proposal or message. Celery acknowledges late,
retries only bounded connection failures, and writes a PII-redacted terminal record to the dead-letter
list. Model calls first retry the configured smaller open model and then use a deterministic grounded
writer. The fallback is visible in usage metadata; degraded output is never represented as a normal
model success.

## 12–14. Product-state defects

Browser testing exposed a hard-coded USD 300 UI floor that could disagree with the graph. Persisted
profile settings are now the single source used by both API and UI. Scheduled searches originally had
a rediscovery/enqueue race; durable seen-job keys now deduplicate the unit of work. Finally, in-memory
approval would have been lost on API restart. The API now seeds a durable START checkpoint, workers
verify tenant/user/job identity before resume, and Postgres integration tests restart the execution
path and assert exactly one effect.

## 15–16. Model reasoning and citation-contract defects

The first two-model writer pass exposed two failures before model promotion. Qwen3's default thinking
mode spent several minutes on a small structured-writing request, and a bounded retry showed that
“concise” did not prevent an overlong, truncated JSON response. The production Ollama request now sets
`think: false`, caps completion at 1,024 tokens, and the prompt specifies 180-word proposals and
80-word screening answers. Unit tests assert those request controls.

The first completed comparison then showed that both models could discuss evidence IDs without using
the verifier's exact bracket syntax; some also inferred aggregate win-rate or track-record claims from
individual past proposals. The writer contract now requires exact plain `[evidence-id]` citations,
forbids placeholders, Markdown links and aggregate extrapolation, and the verifier detects uncited
success, track-record, past-project and past-proposal prose. The final model comparison reruns the same
fixed jobs after these safety corrections; earlier outputs are treated as debugging evidence, not as
the reportable model result.

## Remaining evaluation gaps

This analysis does not invent evidence that requires people, credentials, or instructor data. The
blind proposal panel and 30-item calibration set are prepared but unscored. Live Upwork/GitHub
validation, public trace links, and hidden attacks remain pending. The bounded model-backed
supervisor/ReAct comparison is complete and separately labelled synthetic. Exact commands and
ownership are tracked in
`docs/SUBMISSION_CHECKLIST.md`.
