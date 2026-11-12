from __future__ import annotations

from agent.handoffs import EvidenceItem
from rag.index.memory import InMemoryEvidenceIndex, tokenize
from rag.variants.v2_hybrid import retrieve as hybrid_retrieve


def _cross_score(query: str, item: EvidenceItem) -> float:
    query_tokens = set(tokenize(query))
    document_tokens = set(tokenize(" ".join([item.title, item.text, *item.skills])))
    coverage = len(query_tokens.intersection(document_tokens)) / max(1, len(query_tokens))
    specificity = len(query_tokens.intersection(document_tokens)) / max(1, len(document_tokens))
    return coverage * 0.8 + specificity * 0.2


def retrieve(query: str, index: InMemoryEvidenceIndex, k: int = 5) -> list[EvidenceItem]:
    candidates = hybrid_retrieve(query, index, k=max(20, k * 4))
    scored = [(_cross_score(query, item), item) for item in candidates]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item.model_copy(update={"relevance_score": score}) for score, item in scored[:k]]
