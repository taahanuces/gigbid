import json
from pathlib import Path

import pytest

from agent.handoffs import EvidenceItem
from agent.nodes.analyst import analyze_job
from rag.index.memory import InMemoryEvidenceIndex
from rag.retriever import retrieve_for_job
from rag.variants.v2_hybrid import retrieve as hybrid_retrieve

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "variant",
    ["v0_naive", "v1_requirements", "v2_hybrid", "v3_rerank", "v8_corrective"],
)
def test_retrieval_variants_return_relevant_evidence(variant: str) -> None:
    job = analyze_job(json.loads((ROOT / "evals/datasets/smoke_jobs.json").read_text())[0])
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((ROOT / "evals/datasets/smoke_portfolio.json").read_text())
    ]
    results = retrieve_for_job(job, InMemoryEvidenceIndex(evidence), variant=variant, k=2)
    assert results
    assert results[0].evidence_id == "ev-demand-001"


def test_hybrid_retrieval_caps_past_proposal_dominance() -> None:
    evidence = [
        EvidenceItem(
            evidence_id=f"proposal-{index}",
            tenant_id="demo",
            persona="data",
            type="past_proposal",
            title="Python forecasting proposal",
            text="Proposed a Python forecasting pipeline.",
            source="test",
            skills=["Python", "forecasting"],
        )
        for index in range(5)
    ]
    evidence.extend(
        [
            EvidenceItem(
                evidence_id="case-1",
                tenant_id="demo",
                persona="data",
                type="case_study",
                title="Python forecasting case study",
                text="Built and validated a Python forecasting pipeline.",
                source="test",
                skills=["Python", "forecasting"],
            ),
            EvidenceItem(
                evidence_id="review-1",
                tenant_id="demo",
                persona="data",
                type="client_review",
                title="Forecasting client review",
                text="Praised the validated forecasting handoff.",
                source="test",
                skills=["forecasting"],
            ),
        ]
    )

    results = hybrid_retrieve(
        "Python forecasting pipeline", InMemoryEvidenceIndex(evidence), k=3
    )

    assert sum(item.type == "past_proposal" for item in results) <= 1
    assert any(item.type == "case_study" for item in results)
