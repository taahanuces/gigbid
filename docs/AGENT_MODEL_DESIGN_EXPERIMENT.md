# Model-Backed Agent-Design Experiment

## Frozen protocol

This study complements, rather than replaces, the 50-job deterministic control baseline. It runs the
hand-built, supervisor-style and ReAct-style control policies through real local model calls on the
same six authored GigSim scenarios: one direct job and one planted attack for each of the AI/ML,
data-analysis and full-stack personas. Every row uses V2 evidence, temperature 0, seed 4016, the same
Connects/policy limits, at most three controller attempts and no external write.

Both pinned writer candidates were tested: Qwen3 4B Q4_K_M
(`359d7dd4…fae7`) and Llama 3.1 8B Q4_K_M (`46e0c10c…666e`) on an Apple M4 with 11.8 GiB unified GPU
reported by Ollama. The frozen failure schedule injects one transient before the first model call on
the same full-stack attack row for every model and architecture. Raw controller outputs, including
invalid outputs, tokens, failures, plans and synthetic outcomes are preserved in
`evals/results/agent_model_design.json`.

## Results

| Model | Policy | Controller completion | Final decision/F1 | Final safety violations | Tokens in/out | p95 latency | Retries / failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3 4B | Hand-built | 0.833 | 1.00 / 1.00 | 0 | 3,556 / 1,257 | 30.0 s | 3 / 4 |
| Qwen3 4B | Supervisor | 1.000 | 1.00 / 1.00 | 0 | 2,938 / 409 | 4.1 s | 1 / 1 |
| Qwen3 4B | ReAct-style | 0.833 | 1.00 / 1.00 | 0 | 3,658 / 1,669 | 19.0 s | 2 / 3 |
| Llama 3.1 8B | Hand-built | 1.000 | 1.00 / 1.00 | 0 | 2,620 / 217 | 4.2 s | 1 / 1 |
| Llama 3.1 8B | Supervisor | 1.000 | 1.00 / 1.00 | 0 | 2,884 / 326 | 7.5 s | 1 / 1 |
| Llama 3.1 8B | ReAct-style | 1.000 | 1.00 / 1.00 | 0 | 3,076 / 1,121 | 16.3 s | 1 / 1 |

All final actions matched the authored bid/skip labels, and no attack case reached a bid. The three
safe proposals per policy all received a synthetic reply; one of three was hired by the deterministic
GigSim rule engine. Those rates are identical because proposal text and simulator rules were held
constant to isolate controller behavior. They are not estimates of real marketplace outcomes.

Qwen's hand-built prompt echoed the entire untrusted observation instead of returning the requested
action on the full-stack direct job for all three attempts. Qwen's ReAct prompt did the same twice on
the scheduled attack after the injected transient. The bounded deterministic fallback still produced
the correct safe action, but controller completion is reported as 0.833 rather than hiding the schema
failure. Llama completed every model response. The registered per-model selection rule chose the
supervisor prompt for Qwen and the hand-built prompt for Llama. ReAct used the most output tokens and
had the highest p95 latency for both models.

## Engineering decision

The production graph remains hand-written and deterministic at the orchestration boundary. The
model-backed policies produced no decision, safety or synthetic-outcome gain over that graph, while
introducing schema, token and latency failure modes. If a Qwen model router is later required, the
supervisor-shaped contract is the strongest measured prompt in this small slice; it is not evidence
to replace the explicit graph, checkpoint joins or approval interrupts.

This is a bounded single-turn structured-plan comparison, not long-horizon autonomous ReAct behavior.
It is synthetic, small, and host-specific, but it closes the local architecture experiment honestly:
model behavior, deterministic safety fallback and rule-engine outcomes are reported separately.

## Reproduction

```bash
make eval-agent-model-design
```

The frozen configuration is `evals/datasets/agent_model_design_jobs.json`; the deterministic public
baseline remains in `evals/results/agent_design.json` and `docs/AGENT_DESIGN_EXPERIMENT.md`.
