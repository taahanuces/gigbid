from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from agent.handoffs import EvidenceItem
from agent.nodes.analyst import analyze_job
from agent.nodes.decision import decide_bid
from agent.nodes.fit_matcher import match_fit
from agent.nodes.risk_assessor import assess_risk
from evals.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ["v0_naive", "v1_requirements", "v2_hybrid", "v3_rerank", "v8_corrective"]


def run_smoke() -> dict[str, object]:
    jobs = json.loads((ROOT / "evals/datasets/smoke_jobs.json").read_text(encoding="utf-8"))
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads(
            (ROOT / "evals/datasets/smoke_portfolio.json").read_text(encoding="utf-8")
        )
    ]
    index = InMemoryEvidenceIndex(evidence)
    gold = {
        "job-forecast-001": {"ev-demand-001", "ev-report-002"},
        "job-risk-002": set(),
    }
    variant_results: dict[str, dict[str, float]] = {}
    latencies: dict[str, list[float]] = {variant: [] for variant in VARIANTS}
    for variant in VARIANTS:
        recalls: list[float] = []
        reciprocal_ranks: list[float] = []
        ndcgs: list[float] = []
        for raw_job in jobs:
            job = analyze_job(raw_job)
            start = time.perf_counter()
            retrieved = retrieve_for_job(job, index, variant=variant, k=5)
            latencies[variant].append((time.perf_counter() - start) * 1000)
            ids = [item.evidence_id for item in retrieved]
            relevant = gold[job.job_id]
            recalls.append(recall_at_k(ids, relevant, 5))
            reciprocal_ranks.append(reciprocal_rank(ids, relevant))
            ndcgs.append(ndcg_at_k(ids, relevant, 10))
        variant_results[variant] = {
            "evidence_recall_at_5": statistics.mean(recalls),
            "mrr": statistics.mean(reciprocal_ranks),
            "ndcg_at_10": statistics.mean(ndcgs),
            "p95_latency_ms": max(latencies[variant]),
        }

    decisions: list[dict[str, object]] = []
    for raw_job in jobs:
        job = analyze_job(raw_job)
        risk = assess_risk(job)
        retrieved = retrieve_for_job(job, index, variant="v8_corrective", k=5)
        fit = match_fit(job, retrieved)
        decision = decide_bid(job, risk, fit)
        decisions.append(
            {
                "job_id": job.job_id,
                "action": decision.action,
                "risk_score": risk.score,
                "fit_score": fit.score,
                "injection_detected": bool(risk.ignored_instructions),
            }
        )
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset": "synthetic smoke only - not reportable R&D evidence",
            "python": platform.python_version(),
            "job_count": len(jobs),
        },
        "rag": variant_results,
        "decisions": decisions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output", default="evals/results/smoke.json")
    args = parser.parse_args()
    if not args.smoke:
        raise SystemExit(
            "Full evaluation requires the instructor dev set. Use --smoke for local verification."
        )
    result = run_smoke()
    output = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
