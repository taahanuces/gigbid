from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from agent.handoffs import EvidenceItem, ProposalClaim
from agent.nodes.analyst import analyze_job
from agent.nodes.fit_matcher import match_fit
from agent.nodes.pricing import price_job
from agent.nodes.risk_assessor import assess_risk
from agent.nodes.writer import draft_proposal
from evals.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job
from rag.verify import verify_claims

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ("v0_naive", "v1_requirements", "v2_hybrid", "v3_rerank", "v8_corrective")


class EvalRow(TypedDict):
    job_id: str
    persona: str
    job_type: str
    variant: str
    recall_at_5: float
    mrr: float
    ndcg_at_10: float
    latency_ms: float
    retrieved_ids: list[str]
    unsupported_before: int
    unsupported_after: int
    attack_unsupported_before: int
    attack_unsupported_after: int


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]


def load_evidence(persona: str) -> list[EvidenceItem]:
    path = ROOT / f"data/processed/personas/{persona}.jsonl"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run python -m data.pipelines.generate_synthetic_personas first."
        )
    return [
        EvidenceItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run() -> dict[str, Any]:
    benchmark = json.loads(
        (ROOT / "evals/datasets/synthetic_rag_benchmark.json").read_text(encoding="utf-8")
    )
    persona_names = sorted({str(item["persona"]) for item in benchmark})
    indexes = {persona: InMemoryEvidenceIndex(load_evidence(persona)) for persona in persona_names}
    rows: list[EvalRow] = []
    grouped: dict[tuple[str, str], list[EvalRow]] = defaultdict(list)

    for raw in benchmark:
        persona = str(raw["persona"])
        relevant = set(map(str, raw["gold_evidence_ids"]))
        job = analyze_job(raw)
        for variant in VARIANTS:
            started = time.perf_counter()
            evidence = retrieve_for_job(job, indexes[persona], variant=variant, k=10)
            latency_ms = (time.perf_counter() - started) * 1_000
            retrieved_ids = [item.evidence_id for item in evidence]
            fit = match_fit(job, evidence)
            risk = assess_risk(job)
            quote = price_job(job, fit, risk, user_floor=300)
            proposal = draft_proposal(job, fit, evidence, quote)
            verification = verify_claims(proposal, evidence)
            unsupported_sentence = "I guarantee a 300% return within one week."
            attacked_proposal = proposal.model_copy(
                update={
                    "cover_letter": f"{proposal.cover_letter}\n\n{unsupported_sentence}",
                    "claims": [
                        *proposal.claims,
                        ProposalClaim(
                            claim_id="seeded-unsupported-claim",
                            sentence=unsupported_sentence,
                            evidence_ids=[],
                        ),
                    ],
                }
            )
            attack_verification = verify_claims(attacked_proposal, evidence)
            row: EvalRow = {
                "job_id": job.job_id,
                "persona": persona,
                "job_type": raw["job_type"],
                "variant": variant,
                "recall_at_5": recall_at_k(retrieved_ids, relevant, 5),
                "mrr": reciprocal_rank(retrieved_ids, relevant),
                "ndcg_at_10": ndcg_at_k(retrieved_ids, relevant, 10),
                "latency_ms": latency_ms,
                "retrieved_ids": retrieved_ids,
                "unsupported_before": verification.unsupported_before,
                "unsupported_after": verification.unsupported_after,
                "attack_unsupported_before": attack_verification.unsupported_before,
                "attack_unsupported_after": attack_verification.unsupported_after,
            }
            rows.append(row)
            grouped[(persona, variant)].append(row)

    by_persona: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for (persona, variant), items in grouped.items():
        latencies = [float(item["latency_ms"]) for item in items]
        by_persona[persona][variant] = {
            "jobs": float(len(items)),
            "evidence_recall_at_5": statistics.mean(float(item["recall_at_5"]) for item in items),
            "mrr": statistics.mean(float(item["mrr"]) for item in items),
            "ndcg_at_10": statistics.mean(float(item["ndcg_at_10"]) for item in items),
            "unsupported_claims_before": statistics.mean(
                int(item["unsupported_before"]) for item in items
            ),
            "unsupported_claims_after": statistics.mean(
                int(item["unsupported_after"]) for item in items
            ),
            "seeded_attack_unsupported_before": statistics.mean(
                int(item["attack_unsupported_before"]) for item in items
            ),
            "seeded_attack_unsupported_after": statistics.mean(
                int(item["attack_unsupported_after"]) for item in items
            ),
            "p50_latency_ms": percentile(latencies, 0.50),
            "p95_latency_ms": percentile(latencies, 0.95),
        }

    overall: dict[str, dict[str, float]] = {}
    for variant in VARIANTS:
        items = [item for item in rows if item["variant"] == variant]
        latencies = [float(item["latency_ms"]) for item in items]
        overall[variant] = {
            "jobs": float(len(items)),
            "evidence_recall_at_5": statistics.mean(float(item["recall_at_5"]) for item in items),
            "mrr": statistics.mean(float(item["mrr"]) for item in items),
            "ndcg_at_10": statistics.mean(float(item["ndcg_at_10"]) for item in items),
            "unsupported_claims_before": statistics.mean(
                int(item["unsupported_before"]) for item in items
            ),
            "unsupported_claims_after": statistics.mean(
                int(item["unsupported_after"]) for item in items
            ),
            "seeded_attack_unsupported_before": statistics.mean(
                int(item["attack_unsupported_before"]) for item in items
            ),
            "seeded_attack_unsupported_after": statistics.mean(
                int(item["attack_unsupported_after"]) for item in items
            ),
            "p50_latency_ms": percentile(latencies, 0.50),
            "p95_latency_ms": percentile(latencies, 0.95),
        }

    baseline = overall["v0_naive"]["evidence_recall_at_5"]
    hypothesis_passed = all(
        overall[variant]["evidence_recall_at_5"] >= baseline
        for variant in ("v1_requirements", "v2_hybrid", "v3_rerank")
    )
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_origin": "synthetic",
            "generator_version": "gigbid-personas-v1",
            "benchmark_jobs": len(benchmark),
            "reportable_scope": (
                "experiment plumbing only; not real outcomes or instructor dev data"
            ),
            "judge_score": None,
            "gigsim_reply_rate": None,
        },
        "hypothesis": {
            "statement": (
                "V1, V2 and V3 each match or exceed V0 Recall@5 on the synthetic benchmark."
            ),
            "passed": hypothesis_passed,
        },
        "overall": overall,
        "by_persona": dict(by_persona),
        "jobs": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evals/results/synthetic_rag.json")
    args = parser.parse_args()
    result = run()
    destination = ROOT / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
