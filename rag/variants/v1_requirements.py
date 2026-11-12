from __future__ import annotations

from agent.handoffs import EvidenceItem, JobSpec
from rag.index.memory import InMemoryEvidenceIndex


def retrieve(job: JobSpec, index: InMemoryEvidenceIndex, k: int = 5) -> list[EvidenceItem]:
    requirements = list(dict.fromkeys([*job.required_skills, *job.deliverables]))
    best: dict[str, EvidenceItem] = {}
    for requirement in requirements:
        for item in index.search_dense(requirement, k=k):
            current = best.get(item.evidence_id)
            if current is None or item.relevance_score > current.relevance_score:
                best[item.evidence_id] = item
    return sorted(best.values(), key=lambda item: item.relevance_score, reverse=True)[:k]
