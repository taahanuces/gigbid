from mcp import Client
from pytest import MonkeyPatch

from agent.handoffs import EvidenceItem
from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter
from mcp_servers.marketplace.server import build_server as build_marketplace
from mcp_servers.portfolio.server import build_server as build_portfolio
from mcp_servers.portfolio.service import PortfolioService


async def test_portfolio_tool_over_real_inprocess_mcp_protocol() -> None:
    evidence = EvidenceItem(
        evidence_id="case-1",
        tenant_id="tenant-a",
        persona="analyst",
        type="case_study",
        title="Demand forecast",
        text="Built a demand forecast in Python.",
        source="case.md",
        skills=["Python", "Forecasting"],
    )
    async with Client(build_portfolio(PortfolioService([evidence]))) as client:
        result = await client.call_tool(
            "search_evidence",
            {"requirement": "Python demand forecast", "k": 3},
        )
    assert result.is_error is False
    assert result.structured_content["result"][0]["evidence_id"] == "case-1"


async def test_marketplace_dry_run_has_no_side_effect_over_mcp_protocol() -> None:
    adapter = InMemoryMarketplaceAdapter(
        jobs=[{"job_id": "job-1", "connects_cost": 7}],
        connects=25,
    )
    async with Client(build_marketplace(adapter)) as client:
        result = await client.call_tool(
            "create_proposal_draft",
            {
                "input": {
                    "tenant_id": "tenant-a",
                    "trace_id": "trace-12345",
                    "job_id": "job-1",
                    "cover_letter": "A grounded proposal with enough detail.",
                    "idempotency_key": "draft-job-1",
                    "dry_run": True,
                }
            },
        )
    assert result.is_error is False
    assert result.structured_content["preview"]["connects_cost"] == 7
    assert adapter.connects == 25
    assert adapter.proposals == {}


async def test_marketplace_audit_log_carries_trace_and_masks_pii(
    tmp_path, monkeypatch: MonkeyPatch
) -> None:
    audit_path = tmp_path / "marketplace.jsonl"
    monkeypatch.setenv("MCP_AUDIT_LOG", str(audit_path))
    monkeypatch.delenv("MCP_BEARER_TOKEN", raising=False)
    adapter = InMemoryMarketplaceAdapter(
        jobs=[{"job_id": "job-1", "connects_cost": 2}],
        connects=10,
    )
    async with Client(build_marketplace(adapter)) as client:
        result = await client.call_tool(
            "create_proposal_draft",
            {
                "input": {
                    "tenant_id": "tenant-a",
                    "trace_id": "trace-audit-1",
                    "job_id": "job-1",
                    "cover_letter": "Contact test@example.com only inside this redaction test.",
                    "idempotency_key": "audit-job-1",
                    "dry_run": True,
                }
            },
        )
    assert result.is_error is False
    audit_line = audit_path.read_text(encoding="utf-8")
    assert "trace-audit-1" in audit_line
    assert "[REDACTED_EMAIL]" in audit_line
    assert "test@example.com" not in audit_line
