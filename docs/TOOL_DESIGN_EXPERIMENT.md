# Tool-Design Experiment

## Question and task set

The study asks how tool granularity and descriptions affect tool selection, argument construction,
token use and latency. The fixed dataset contains 40 known-call tasks spanning every owned Portfolio,
Marketplace and Workspace operation. Each task has one expected tool and exact arguments in
`evals/datasets/tool_design_tasks.json`.

No selected tool is executed. This isolates interface usability from marketplace state and makes the
write-like tasks safe. The runner uses temperature 0 and seed 4016, and stores every raw selection so
the scoring policy can be audited or changed without rerunning the model.

## Compared designs

| Design | Interface |
|---|---|
| Fine-grained | 14 single-purpose tools with the production descriptions |
| Coarse-grained | 3 server-level action tools, each requiring an operation discriminator and nested arguments |
| Best descriptions | The same 14 single-purpose tools plus explicit “use when / do not use” boundaries |

Tool accuracy requires the selected function name to match. For the coarse design, choosing the right
server-level tool counts as tool selection; choosing the operation is part of argument accuracy.
Argument accuracy requires exact JSON values and types and rejects missing or additional keys, matching
the production tools' `additionalProperties: false` contracts.

## Reproducible run

- Model: local `llama3.1:8b`
- Model digest: `667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29`
- Runtime: Ollama 0.40.7
- Calls: 40 tasks × 3 designs = 120
- Runtime errors: 0
- Result: `evals/results/tool_design.json`

| Design | Tool accuracy | Argument accuracy | Mean tokens/task | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|
| Fine-grained | 100% | 60% | 1,229.6 | 2.17 s | 5.49 s |
| Coarse-grained | 80% | 15% | 411.0 | 2.85 s | 6.06 s |
| Best descriptions | 100% | 50% | 1,424.0 | 3.06 s | 7.74 s |

## Interpretation and shipped choice

Fine-grained production descriptions are the best observed trade-off: they tied the enhanced
descriptions on perfect tool selection, achieved the highest exact argument accuracy, and used fewer
tokens with lower latency. The coarse interface saved prompt tokens but shifted schema knowledge into
an untyped nested object; the model frequently renamed fields, omitted tenant identifiers or selected
no tool. Longer boundary descriptions did not improve selection because the short descriptions were
already unambiguous, and their argument accuracy was four tasks lower.

GigBid therefore ships the fine-grained interfaces and agent-specific allowlists. The 60% exact
argument score also justifies retaining Pydantic validation, dry-run defaults and approval gates rather
than trusting model-produced arguments directly.

## Limitations

This is one deterministic pass on one local 8B model and 40 authored tasks. It measures known-call
selection, not task completion, tool-result interpretation or user satisfaction. The task mix is
balanced for interface coverage rather than sampled from production traffic. A stronger follow-up
would repeat seeds and models, blind the task wording, and report paired confidence intervals.
