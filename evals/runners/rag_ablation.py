from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.handoffs import EvidenceItem, JobSpec
from agent.nodes.analyst import analyze_job
from evals.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from rag.index.memory import InMemoryEvidenceIndex
from rag.variants.v0_naive import retrieve as dense_retrieve
from rag.variants.v2_hybrid import retrieve as hybrid_retrieve

ROOT = Path(__file__).resolve().parents[2]
Ablation = Callable[[JobSpec, InMemoryEvidenceIndex, int], list[EvidenceItem]]


def _query(job: JobSpec) -> str:
    return " ".join(
        [job.title, job.description, *job.required_skills, *job.deliverables, *job.hidden_needs]
    )


def dense_only(job: JobSpec, index: InMemoryEvidenceIndex, k: int) -> list[EvidenceItem]:
    return dense_retrieve(_query(job), index, k=k)


def lexical_only(job: JobSpec, index: InMemoryEvidenceIndex, k: int) -> list[EvidenceItem]:
    return index.search_bm25(_query(job), k=k)


def hybrid_rrf(job: JobSpec, index: InMemoryEvidenceIndex, k: int) -> list[EvidenceItem]:
    return hybrid_retrieve(_query(job), index, k=k)


ABLATIONS: dict[str, Ablation] = {
    "dense_only": dense_only,
    "lexical_only": lexical_only,
    "hybrid_rrf": hybrid_rrf,
}


def _load_index(persona: str) -> InMemoryEvidenceIndex:
    path = ROOT / "data/processed/personas" / f"{persona}.jsonl"
    evidence = [
        EvidenceItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return InMemoryEvidenceIndex(evidence)


def _summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "jobs": float(len(rows)),
        "evidence_recall_at_5": statistics.mean(row["recall_at_5"] for row in rows),
        "mrr": statistics.mean(row["mrr"] for row in rows),
        "ndcg_at_10": statistics.mean(row["ndcg_at_10"] for row in rows),
        "p95_latency_ms": sorted(row["latency_ms"] for row in rows)[
            round((len(rows) - 1) * 0.95)
        ],
    }


def run() -> dict[str, Any]:
    benchmark = json.loads(
        (ROOT / "evals/datasets/synthetic_rag_benchmark.json").read_text(encoding="utf-8")
    )
    personas = sorted({str(item["persona"]) for item in benchmark})
    indexes = {persona: _load_index(persona) for persona in personas}
    rows: list[dict[str, Any]] = []
    for raw in benchmark:
        persona = str(raw["persona"])
        relevant = set(map(str, raw["gold_evidence_ids"]))
        job = analyze_job(raw)
        for name, retriever in ABLATIONS.items():
            started = time.perf_counter()
            evidence = retriever(job, indexes[persona], 10)
            latency_ms = (time.perf_counter() - started) * 1_000
            retrieved = [item.evidence_id for item in evidence]
            rows.append(
                {
                    "job_id": job.job_id,
                    "persona": persona,
                    "job_type": str(raw["job_type"]),
                    "ablation": name,
                    "recall_at_5": recall_at_k(retrieved, relevant, 5),
                    "mrr": reciprocal_rank(retrieved, relevant),
                    "ndcg_at_10": ndcg_at_k(retrieved, relevant, 10),
                    "latency_ms": latency_ms,
                }
            )

    overall = {
        name: _summary([row for row in rows if row["ablation"] == name])
        for name in ABLATIONS
    }
    by_persona: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    by_job_type: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for persona in personas:
        for name in ABLATIONS:
            by_persona[persona][name] = _summary(
                [
                    row
                    for row in rows
                    if row["persona"] == persona and row["ablation"] == name
                ]
            )
    job_types = sorted({str(row["job_type"]) for row in rows})
    for job_type in job_types:
        for name in ABLATIONS:
            by_job_type[job_type][name] = _summary(
                [
                    row
                    for row in rows
                    if row["job_type"] == job_type and row["ablation"] == name
                ]
            )
    return {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "data_origin": "synthetic",
            "jobs": len(benchmark),
            "shipped_variant": "v2_hybrid",
            "interpretation_boundary": (
                "Component ablation on authored synthetic relevance labels; no real outcome claim."
            ),
        },
        "hypothesis": {
            "statement": (
                "Type-diverse hybrid RRF improves nDCG@10 over dense-only "
                "and lexical-only retrieval."
            ),
            "passed": (
                overall["hybrid_rrf"]["ndcg_at_10"]
                > max(
                    overall["dense_only"]["ndcg_at_10"],
                    overall["lexical_only"]["ndcg_at_10"],
                )
            ),
        },
        "overall": overall,
        "by_persona": dict(by_persona),
        "by_job_type": dict(by_job_type),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evals/results/rag_ablation.json")
    args = parser.parse_args()
    destination = ROOT / args.output
    destination.write_text(json.dumps(run(), indent=2), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
