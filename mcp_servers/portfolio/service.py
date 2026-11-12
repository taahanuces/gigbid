from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from agent.handoffs import EvidenceItem
from rag.index.memory import InMemoryEvidenceIndex


class PortfolioService:
    def __init__(
        self,
        evidence: list[EvidenceItem] | None = None,
        *,
        tenant_id: str | None = None,
        persona: str | None = None,
    ) -> None:
        scoped = [
            item
            for item in evidence or []
            if (tenant_id is None or item.tenant_id == tenant_id)
            and (persona is None or item.persona == persona)
        ]
        self.index = InMemoryEvidenceIndex(scoped)

    @classmethod
    def from_jsonl(
        cls,
        paths: Iterable[Path],
        *,
        tenant_id: str | None = None,
        persona: str | None = None,
    ) -> PortfolioService:
        evidence: list[EvidenceItem] = []
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(f"Portfolio evidence file does not exist: {path}")
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    evidence.append(EvidenceItem.model_validate_json(line))
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid portfolio evidence in {path}:{line_number}: {exc}"
                    ) from exc
        return cls(evidence, tenant_id=tenant_id, persona=persona)

    def search_evidence(
        self,
        requirement: str,
        *,
        k: int = 5,
        filters: dict[str, str] | None = None,
    ) -> list[EvidenceItem]:
        candidates = self.index.search_dense(requirement, k=max(k * 3, k))
        filters = filters or {}
        filtered = [
            item
            for item in candidates
            if all(str(getattr(item, key, None)) == value for key, value in filters.items())
        ]
        return filtered[:k]

    def get_case_study(self, evidence_id: str) -> EvidenceItem:
        item = self.index.get(evidence_id)
        if item is None or item.type != "case_study":
            raise KeyError(f"Unknown case study: {evidence_id}")
        return item

    def get_proposal(self, evidence_id: str) -> EvidenceItem:
        item = self.index.get(evidence_id)
        if item is None or item.type != "proposal":
            raise KeyError(f"Unknown proposal: {evidence_id}")
        return item

    def list_skills(self) -> list[str]:
        return sorted({skill for item in self.index.all() for skill in item.skills})
