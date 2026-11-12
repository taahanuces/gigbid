from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from agent.memory.promotion_rules import (
    OutcomeObservation,
    StyleEditObservation,
    promote_outcome_strategy,
    promote_style_pattern,
)

MemoryKind = Literal["style", "outcome"]
LABEL_PATTERN = re.compile(r"[^A-Za-z0-9_-]")


class PromotedMemory(BaseModel):
    key: str
    kind: MemoryKind
    value: str
    evidence_count: int = Field(ge=1)
    category: str | None = None
    promoted_at: datetime


def infer_style_patterns(original: str, edited: str) -> list[str]:
    """Extract conservative, inspectable style signals from an explicit user edit."""

    before = original.strip()
    after = edited.strip()
    if before == after:
        return []
    patterns: list[str] = []
    before_words = before.split()
    after_words = after.split()
    if before_words and len(after_words) <= len(before_words) * 0.8:
        patterns.append("prefer_concise_proposals")
    generic_openings = ("hello", "dear hiring manager", "i am excited", "i'm excited")
    before_lower = before.lower()
    after_lower = after.lower()
    if any(before_lower.startswith(item) for item in generic_openings) and not any(
        after_lower.startswith(item) for item in generic_openings
    ):
        patterns.append("avoid_generic_openings")
    before_bullets = sum(line.lstrip().startswith(("-", "*", "•")) for line in before.splitlines())
    after_bullets = sum(line.lstrip().startswith(("-", "*", "•")) for line in after.splitlines())
    if after_bullets > before_bullets:
        patterns.append("prefer_bulleted_structure")
    if after_lower.count("you") > before_lower.count("you"):
        patterns.append("prefer_client_focused_language")
    return patterns or ["manual_style_edit"]


def _label(value: str) -> str:
    return LABEL_PATTERN.sub("_", value)[:120] or "unknown"


def _key(*parts: object) -> str:
    digest = hashlib.sha256("\x1f".join(map(str, parts)).encode("utf-8")).hexdigest()[:24]
    return f"memory-{digest}"


class LongTermMemory:
    """Tenant-scoped observations with thresholded, reversible promotion."""

    def __init__(
        self,
        store: BaseStore,
        *,
        tenant_id: str,
        user_id: str,
        style_minimum_consistent_edits: int = 3,
        outcome_minimum_observations: int = 5,
        outcome_minimum_reply_rate: float = 0.3,
    ) -> None:
        self.store = store
        self.base = ("gigbid", _label(tenant_id), _label(user_id), "memory")
        self.style_minimum = style_minimum_consistent_edits
        self.outcome_minimum = outcome_minimum_observations
        self.outcome_reply_rate = outcome_minimum_reply_rate

    async def record_style_observation(
        self,
        *,
        thread_id: str,
        pattern: str,
        accepted: bool = True,
    ) -> PromotedMemory | None:
        namespace = (*self.base, "observations", "style")
        observation = StyleEditObservation(
            pattern=pattern,
            accepted=accepted,
            source_thread_id=thread_id,
        )
        await self.store.aput(
            namespace,
            _key(thread_id, pattern),
            observation.model_dump(mode="json"),
            index=False,
        )
        items = await self.store.asearch(namespace, limit=1_000)
        observations = [StyleEditObservation.model_validate(item.value) for item in items]
        promoted = promote_style_pattern(
            observations,
            minimum_consistent_edits=self.style_minimum,
        )
        if promoted != pattern:
            return None
        evidence_count = sum(item.accepted and item.pattern == promoted for item in observations)
        memory = PromotedMemory(
            key=_key("promoted", "style", promoted),
            kind="style",
            value=promoted,
            evidence_count=evidence_count,
            promoted_at=datetime.now(UTC),
        )
        await self.store.aput(
            (*self.base, "promoted", "style"),
            memory.key,
            memory.model_dump(mode="json"),
            index=False,
        )
        return memory

    async def record_outcome(
        self,
        observation: OutcomeObservation,
    ) -> PromotedMemory | None:
        category = _label(observation.category)
        namespace = (*self.base, "observations", "outcome", category)
        observation_key = _key(
            observation.job_id or "unknown-job",
            observation.category,
            observation.strategy,
        )
        await self.store.aput(
            namespace,
            observation_key,
            observation.model_dump(mode="json"),
            index=False,
        )
        items = await self.store.asearch(namespace, limit=5_000)
        observations = [OutcomeObservation.model_validate(item.value) for item in items]
        promoted = promote_outcome_strategy(
            observations,
            minimum_observations=self.outcome_minimum,
            minimum_reply_rate=self.outcome_reply_rate,
        )
        if promoted is None:
            return None
        evidence_count = sum(item.strategy == promoted for item in observations)
        memory = PromotedMemory(
            key=_key("promoted", "outcome", category, promoted),
            kind="outcome",
            category=observation.category,
            value=promoted,
            evidence_count=evidence_count,
            promoted_at=datetime.now(UTC),
        )
        await self.store.aput(
            (*self.base, "promoted", "outcome"),
            memory.key,
            memory.model_dump(mode="json"),
            index=False,
        )
        return memory

    async def list_promoted(self, *, limit: int = 100) -> list[PromotedMemory]:
        items = await self.store.asearch((*self.base, "promoted"), limit=limit)
        memories = [PromotedMemory.model_validate(item.value) for item in items]
        return sorted(memories, key=lambda item: item.promoted_at, reverse=True)

    async def list_observations(
        self, kind: MemoryKind, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        items = await self.store.asearch((*self.base, "observations", kind), limit=limit)
        return [{"key": item.key, **dict(item.value)} for item in items]

    async def delete_promoted(self, kind: MemoryKind, key: str) -> None:
        await self.store.adelete((*self.base, "promoted", kind), key)
