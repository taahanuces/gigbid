# Agent-Design Experiment

## Scope

The committed benchmark compares three control policies on the same 50 jobs:

- the shipped hand-built workflow with an explicit risk/fit join;
- a supervisor policy that delegates each specialist sequentially; and
- a ReAct-style policy that alternates explicit thought and action records until it can decide.

The sample is reproducibly selected from the real public 2023 development split: 10 jobs containing
preprocessing-detected injection phrases and 40 ordinary jobs, sampled round-robin across job
categories. All policies use the same deterministic nodes, V0 retrieval and explicitly synthetic
portfolio corpus, and no write tool is available. The selected pseudonymous IDs and provenance are in
`evals/datasets/agent_design_jobs.json`.

## Results

The machine-readable result is `evals/results/agent_design.json`.

| Policy | Completion | Injection recall (10 probes) | External writes | Mean control steps | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| Hand-built | 100% | 100% | 0 | 4 | 7.03 ms | 7.19 ms |
| Supervisor | 100% | 100% | 0 | 8 | 6.96 ms | 7.22 ms |
| ReAct-style | 100% | 100% | 0 | 8 | 6.97 ms | 7.15 ms |

All policies agreed on every decision because they deliberately share analysis, risk, retrieval, fit
and decision functions. Each produced 45 skips, 4 watches and 1 bid. That distribution is descriptive,
not accuracy: this public corpus has no authoritative decision labels, and the three synthetic
portfolios cover only the assignment personas.

## Decision

The hand-built workflow remains the shipped architecture. It reaches the same deterministic result
with half the control steps, has explicit joins and approval boundaries, and is easier to replay and
test. A supervisor or ReAct loop has no demonstrated benefit in this bounded workflow and introduces
additional routing/model opportunities for failure.

## Reporting boundary

This remains the deterministic public-data control-policy baseline: its ReAct-style and supervisor
routers do not use model planning, and Kaggle supplies no replies, hires or decision labels. The
separate frozen six-job, two-model GigSim study now reports real controller calls, costs, retries,
failures and explicitly synthetic outcomes in `docs/AGENT_MODEL_DESIGN_EXPERIMENT.md`. The two studies
remain separate so the model-backed result does not rewrite this baseline.
