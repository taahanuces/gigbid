# Open Writer Model Profile Experiment

## Question and decision rule

Which locally runnable open model should write GigBid proposals after type-diverse V2 retrieval? The
registered selection rule is lexicographic: JSON-schema validity, citation precision, grounding,
personalization, then lower p95 latency. Safety/validity therefore cannot be traded for speed.

## Method

- Models: `qwen3:4b` and `llama3.1:8b`, both Q4_K_M, served by local Ollama.
- Hardware: Apple M4 with 11.8 GiB unified GPU memory reported by Ollama.
- Data: nine fixed direct jobs, three per explicitly synthetic persona, from
  `evals/datasets/synthetic_rag_benchmark.json`.
- Context: identical type-diverse V2 top-five evidence and the production `writer.v1.md` prompt.
- Controls: temperature 0, seed 4016, thinking disabled, 1,024-token completion cap, one excluded
  warm-up per model, sequential calls, no external writes and no per-token API fee.
- Artifact: `evals/results/model_profiles.json` contains exact digests, every proposal, error, token
  count, latency and automated assessment.

## Final result

| Metric | Qwen3 4B | Llama 3.1 8B |
| --- | ---: | ---: |
| Successful / total calls | 9 / 9 | 9 / 9 |
| JSON-schema validity | 1.000 | 1.000 |
| Critic pass rate | 1.000 | 1.000 |
| Citation precision | 1.000 | 1.000 |
| Unsupported claims before / after | 0.000 / 0.000 | 0.000 / 0.000 |
| Grounding score | 1.000 | 1.000 |
| Personalization score | **0.630** | 0.556 |
| Mean prompt / completion tokens | 1488.3 / 188.2 | 1425.2 / 300.3 |
| Completion tokens/second | **19.76** | 11.59 |
| p50 / p95 latency | **10.1 / 11.4 s** | 29.6 / 33.5 s |
| Local API cost | USD 0.00 | USD 0.00 |

Exact model digests are `359d7dd4…fae7` for Qwen and `46e0c10c…666e` for Llama. Qwen3 4B wins
after the models tie on every validity and grounding criterion, because it has higher personalization
and lower latency. The default `open` profile therefore routes writer/Critic/liaison to Qwen3 4B and
uses Llama 3.1 8B as the model fallback before the deterministic grounded fallback.

## Failures found before the final run

The first trial exposed default Qwen thinking that ran for minutes on a compact JSON task. A bounded
retry then produced truncated JSON because “concise” had no numeric limit. The production request now
sets `think: false`, caps generation at 1,024 tokens, and specifies 180-word proposals and 80-word
answers. Another trial showed both models paraphrasing citations and extrapolating from past proposals.
The final contract requires exact plain bracket IDs, the retriever caps past-proposal dominance, and
the verifier refuses to treat past proposals alone as proof of delivery. Unit tests cover each repair.

## Limitations

This is a small synthetic development comparison on one host, not a human preference panel or real
marketplace outcome study. Automated grounding checks cannot establish persuasiveness, factual truth
outside the supplied evidence, or production latency on another machine. The required blinded human
panel remains unscored. The separate model-backed hand-built/supervisor/ReAct comparison is reported
in `docs/AGENT_MODEL_DESIGN_EXPERIMENT.md` and retains its small synthetic-slice limitation.
