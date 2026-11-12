from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class StyleEditObservation(BaseModel):
    pattern: str
    accepted: bool
    source_thread_id: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OutcomeObservation(BaseModel):
    category: str
    strategy: str
    replied: bool
    hired: bool = False
    job_id: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def promote_style_pattern(
    observations: list[StyleEditObservation], *, minimum_consistent_edits: int = 3
) -> str | None:
    accepted_patterns = [item.pattern for item in observations if item.accepted]
    if not accepted_patterns:
        return None
    pattern, count = Counter(accepted_patterns).most_common(1)[0]
    return pattern if count >= minimum_consistent_edits else None


def promote_outcome_strategy(
    observations: list[OutcomeObservation],
    *,
    minimum_observations: int = 5,
    minimum_reply_rate: float = 0.3,
) -> str | None:
    if len(observations) < minimum_observations:
        return None
    by_strategy: dict[str, list[OutcomeObservation]] = {}
    for observation in observations:
        by_strategy.setdefault(observation.strategy, []).append(observation)
    eligible = {
        strategy: sum(item.replied for item in items) / len(items)
        for strategy, items in by_strategy.items()
        if len(items) >= minimum_observations
    }
    if not eligible:
        return None
    best_strategy, reply_rate = max(eligible.items(), key=lambda item: item[1])
    return best_strategy if reply_rate >= minimum_reply_rate else None
