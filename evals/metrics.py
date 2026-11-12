from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0 if not retrieved[:k] else 0.0
    return len(set(retrieved[:k]).intersection(relevant)) / len(relevant)


def reciprocal_rank(retrieved: Sequence[str], relevant: set[str]) -> float:
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    gains = [1 if item in relevant else 0 for item in retrieved[:k]]
    dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
    ideal = [1] * min(len(relevant), k)
    idcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(ideal))
    return dcg / idcg if idcg else 1.0


def precision_recall_f1(predictions: Sequence[bool], labels: Sequence[bool]) -> dict[str, float]:
    if len(predictions) != len(labels):
        raise ValueError("Prediction and label sequences must have equal length")
    pairs = list(zip(predictions, labels, strict=True))
    true_positive = sum(prediction and label for prediction, label in pairs)
    false_positive = sum(prediction and not label for prediction, label in pairs)
    false_negative = sum(not prediction and label for prediction, label in pairs)
    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def cohens_kappa(left: Sequence[str], right: Sequence[str]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Both non-empty label sequences must have equal length")
    labels = set(left).union(right)
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / len(left)
    expected = sum(
        (left.count(label) / len(left)) * (right.count(label) / len(right)) for label in labels
    )
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0
