from __future__ import annotations

from agent.handoffs import EvidenceItem, JobSpec
from rag.index.memory import InMemoryEvidenceIndex
from rag.variants import v0_naive, v1_requirements, v2_hybrid, v3_rerank, v8_corrective


def retrieve_for_job(
    job: JobSpec,
    index: InMemoryEvidenceIndex,
    *,
    variant: str,
    k: int = 5,
) -> list[EvidenceItem]:
    query = f"{job.title}\n{job.description}"
    if variant == "v0_naive":
        return v0_naive.retrieve(query, index, k)
    if variant == "v1_requirements":
        return v1_requirements.retrieve(job, index, k)
    if variant == "v2_hybrid":
        return v2_hybrid.retrieve(query, index, k)
    if variant == "v3_rerank":
        return v3_rerank.retrieve(query, index, k)
    if variant == "v8_corrective":
        return v8_corrective.retrieve(job, index, k)
    raise ValueError(f"Unknown retrieval variant: {variant}")
