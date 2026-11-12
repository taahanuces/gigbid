from __future__ import annotations

from agent.handoffs import EvidenceItem
from rag.index.memory import InMemoryEvidenceIndex


def retrieve(query: str, index: InMemoryEvidenceIndex, k: int = 5) -> list[EvidenceItem]:
    candidate_count = max(40, k * 8)
    dense = index.search_dense(query, k=candidate_count)
    lexical = index.search_bm25(query, k=candidate_count)
    scores: dict[str, float] = {}
    items: dict[str, EvidenceItem] = {}
    for ranking in (dense, lexical):
        for rank, item in enumerate(ranking, start=1):
            scores[item.evidence_id] = scores.get(item.evidence_id, 0) + 1 / (60 + rank)
            items[item.evidence_id] = item
    ranked_ids = sorted(scores, key=lambda evidence_id: scores[evidence_id], reverse=True)
    maximum = max(scores.values(), default=1.0)
    selected_ids: list[str] = []
    past_proposal_limit = max(1, k // 3)
    past_proposals = 0
    for evidence_id in ranked_ids:
        item = items[evidence_id]
        if item.type == "past_proposal":
            if past_proposals >= past_proposal_limit:
                continue
            past_proposals += 1
        selected_ids.append(evidence_id)
        if len(selected_ids) >= k:
            break
    return [
        items[evidence_id].model_copy(update={"relevance_score": scores[evidence_id] / maximum})
        for evidence_id in selected_ids
    ]
