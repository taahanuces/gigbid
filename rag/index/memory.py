from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from agent.handoffs import EvidenceItem

TOKEN_PATTERN = re.compile(r"[a-z0-9+#.-]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


class HashingEncoder:
    """Offline deterministic dense encoder for tests and degraded mode."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token, count in Counter(tokenize(text)).items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


class InMemoryEvidenceIndex:
    def __init__(
        self,
        evidence: list[EvidenceItem] | None = None,
        encoder: HashingEncoder | None = None,
    ) -> None:
        self.encoder = encoder or HashingEncoder()
        self._items: dict[str, EvidenceItem] = {}
        self._vectors: dict[str, list[float]] = {}
        self._tokens: dict[str, list[str]] = {}
        for item in evidence or []:
            self.upsert(item)

    def upsert(self, item: EvidenceItem) -> None:
        content = " ".join([item.title, item.text, *item.skills])
        self._items[item.evidence_id] = item
        self._vectors[item.evidence_id] = self.encoder.encode(content)
        self._tokens[item.evidence_id] = tokenize(content)

    def get(self, evidence_id: str) -> EvidenceItem | None:
        return self._items.get(evidence_id)

    def all(self) -> list[EvidenceItem]:
        return list(self._items.values())

    def search_dense(self, query: str, *, k: int = 5) -> list[EvidenceItem]:
        query_vector = self.encoder.encode(query)
        ranked = sorted(
            (
                (max(0.0, cosine(query_vector, vector)), self._items[evidence_id])
                for evidence_id, vector in self._vectors.items()
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        return [item.model_copy(update={"relevance_score": score}) for score, item in ranked[:k]]

    def search_bm25(self, query: str, *, k: int = 5) -> list[EvidenceItem]:
        terms = tokenize(query)
        documents = self._tokens
        count = max(1, len(documents))
        average_length = sum(len(tokens) for tokens in documents.values()) / count
        ranked: list[tuple[float, EvidenceItem]] = []
        for evidence_id, tokens in documents.items():
            frequencies = Counter(tokens)
            score = 0.0
            for term in terms:
                document_frequency = sum(term in document for document in documents.values())
                inverse = math.log(
                    1 + (count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                frequency = frequencies[term]
                denominator = frequency + 1.5 * (
                    1 - 0.75 + 0.75 * len(tokens) / max(1, average_length)
                )
                score += inverse * frequency * 2.5 / max(1e-9, denominator)
            ranked.append((score, self._items[evidence_id]))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        maximum = max((score for score, _ in ranked), default=1.0) or 1.0
        return [
            item.model_copy(update={"relevance_score": min(1.0, score / maximum)})
            for score, item in ranked[:k]
        ]
