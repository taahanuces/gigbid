# Self-Contained Marketplace Simulator

## Purpose and provenance

GigBid includes a GigSim-compatible FastAPI service because the course folder did not contain a
working simulator. `evals/datasets/simulator_fixture.json` contains 300 pseudonymous public jobs drawn
from the version-pinned Apache-2.0 Upwork 60K development split. Public job text, budgets, skills and
client-history fields retain `real_public_dataset` provenance. Hidden client preferences, authored gold
labels and reply/hire decisions are explicitly `synthetic` or `synthetic_rule_based`; they are never
presented as real marketplace outcomes.

The REST service supports jobs, client history, Connects, proposal dry runs, idempotent drafts and
submission, messages, events, deterministic fault injection and outcome inspection. The same engine is
available through an in-process marketplace-port adapter so evaluations do not depend on network
timing. The Marketplace MCP server uses the REST adapter in Compose.

## Fixed outcome study

`evals/runners/simulator_outcomes.py` evaluates 30 authored jobs per persona: 24 portfolio-aligned bid
cases and six planted free-work, off-platform and prompt-injection attacks. The outcome engine scores
skill alignment, job-specific wording, evidence citations, length, budget compatibility and hidden
client thresholds. Thresholds vary deterministically by job, preventing every valid proposal from
receiving the same outcome.

| Persona | Bid/skip F1 | Scam precision/recall | Price in band | Reply rate | Hire rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| AI/ML engineer | 1.000 | 1.000 / 1.000 | 1.000 | 0.667 | 0.583 |
| Full-stack developer | 1.000 | 1.000 / 1.000 | 1.000 | 0.917 | 0.667 |
| Data analyst | 1.000 | 1.000 / 1.000 | 1.000 | 0.708 | 0.542 |

All 72 submitted proposals retained zero unsupported claims after verification. These perfect control
and safety scores are acceptance results on deliberately authored scenarios, not evidence of external
generalisation. Reply and hire rates are useful for regression and architecture comparisons only. The
machine-readable source is `evals/results/simulator_outcomes.json`.

## Reproduction

- `make simulator-data` regenerates the 300-job public/synthetic service fixture after public-data
  preprocessing.
- `make simulator` starts the REST service on port 8081.
- `make eval-simulator-outcomes` regenerates the fixed 90-run outcome result.
- `python -m evals.runners.check_regression` applies the CI quality thresholds.

## Limitations

The outcome rules are deterministic and substantially simpler than a real client. Public postings do
not contain true reply/hire counterfactuals. The simulator is suitable for repeatable engineering,
safety and regression tests, but it cannot establish that a proposal strategy will work on Upwork.
