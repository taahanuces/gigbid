from pathlib import Path

import pytest

from agent.handoffs import DataOrigin, EvidenceItem
from mcp_servers.portfolio.service import PortfolioService


def item(*, evidence_id: str, tenant_id: str, persona: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        tenant_id=tenant_id,
        persona=persona,
        type="case_study",
        title="Grounded case study",
        text="Implemented a FastAPI service with tests.",
        source=f"synthetic://{evidence_id}",
        skills=["FastAPI"],
        data_origin=DataOrigin.SYNTHETIC,
    )


def test_jsonl_loader_applies_tenant_and_persona_scope(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.jsonl"
    records = [
        item(evidence_id="keep", tenant_id="tenant-a", persona="developer"),
        item(evidence_id="wrong-tenant", tenant_id="tenant-b", persona="developer"),
        item(evidence_id="wrong-persona", tenant_id="tenant-a", persona="analyst"),
    ]
    path.write_text("\n".join(record.model_dump_json() for record in records), encoding="utf-8")

    service = PortfolioService.from_jsonl(
        [path], tenant_id="tenant-a", persona="developer"
    )

    assert [loaded.evidence_id for loaded in service.index.all()] == ["keep"]
    assert service.list_skills() == ["FastAPI"]


def test_jsonl_loader_reports_file_and_line_for_invalid_evidence(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"portfolio\.jsonl:1"):
        PortfolioService.from_jsonl([path])


def test_jsonl_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        PortfolioService.from_jsonl([tmp_path / "missing.jsonl"])
