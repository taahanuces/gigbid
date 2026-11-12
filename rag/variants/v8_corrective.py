from __future__ import annotations

from agent.handoffs import EvidenceItem, JobSpec
from rag.index.memory import InMemoryEvidenceIndex
from rag.variants.v1_requirements import retrieve as requirement_retrieve
from rag.variants.v3_rerank import retrieve as rerank_retrieve


def retrieve(
    job: JobSpec,
    index: InMemoryEvidenceIndex,
    k: int = 5,
    minimum_score: float = 0.35,
) -> list[EvidenceItem]:
    first = requirement_retrieve(job, index, k=k)
    if first and sum(item.relevance_score for item in first) / len(first) >= minimum_score:
        return first
    corrective_query = " ".join(
        [job.title, *job.required_skills, *job.deliverables, *job.hidden_needs]
    )
    corrected = rerank_retrieve(corrective_query, index, k=k)
    return [item for item in corrected if item.relevance_score >= minimum_score]
