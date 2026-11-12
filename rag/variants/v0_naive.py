from __future__ import annotations

from agent.handoffs import EvidenceItem
from rag.index.memory import InMemoryEvidenceIndex


def retrieve(query: str, index: InMemoryEvidenceIndex, k: int = 5) -> list[EvidenceItem]:
    """V0: one dense retrieval over the full job post."""
    return index.search_dense(query, k=k)
