from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from agent.handoffs import EvidenceItem
from mcp_servers.auth import bearer_auth
from mcp_servers.portfolio.service import PortfolioService

ROOT = Path(__file__).resolve().parents[2]


def default_portfolio_service() -> PortfolioService:
    configured = os.getenv("PORTFOLIO_DATA_PATHS", "").strip()
    paths = (
        [Path(item.strip()) for item in configured.split(",") if item.strip()]
        if configured
        else sorted((ROOT / "data" / "processed" / "personas").glob("*.jsonl"))
    )
    tenant_id = os.getenv("PORTFOLIO_TENANT_ID", "demo").strip() or None
    persona = os.getenv("PORTFOLIO_PERSONA", "").strip() or None
    return PortfolioService.from_jsonl(paths, tenant_id=tenant_id, persona=persona)


def build_server(service: PortfolioService | None = None) -> MCPServer:
    portfolio = service or default_portfolio_service()
    resource_url = os.getenv("MCP_RESOURCE_URL", "http://localhost:8101/mcp")
    token_verifier, auth = bearer_auth(resource_url)
    server = MCPServer(
        "gigbid-portfolio",
        token_verifier=token_verifier,
        auth=auth,
    )
    read_annotations = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )

    @server.tool(annotations=read_annotations)
    def search_evidence(
        requirement: Annotated[str, Field(min_length=2, max_length=500)],
        k: Annotated[int, Field(ge=1, le=20)] = 5,
        filters: dict[str, str] | None = None,
    ) -> list[EvidenceItem]:
        """Find verified portfolio evidence relevant to one job requirement."""
        return portfolio.search_evidence(requirement, k=k, filters=filters)

    @server.tool(annotations=read_annotations)
    def get_case_study(evidence_id: str) -> EvidenceItem:
        """Load one full case study by its evidence ID."""
        return portfolio.get_case_study(evidence_id)

    @server.tool(annotations=read_annotations)
    def list_skills() -> list[str]:
        """List skills appearing in verified portfolio evidence."""
        return portfolio.list_skills()

    @server.resource("portfolio://case/{evidence_id}")
    def case_resource(evidence_id: str) -> str:
        """Return a complete case study as JSON."""
        return portfolio.get_case_study(evidence_id).model_dump_json(indent=2)

    @server.resource("portfolio://proposal/{evidence_id}")
    def proposal_resource(evidence_id: str) -> str:
        """Return a historical proposal as JSON."""
        return portfolio.get_proposal(evidence_id).model_dump_json(indent=2)

    @server.prompt()
    def answer_screening_question(question: str) -> str:
        """Create an evidence-first task for answering a marketplace screening question."""
        return (
            "Answer the following screening question using only evidence returned by "
            f"search_evidence. Cite every material claim by evidence ID. Question: {question}"
        )

    return server


mcp = build_server()


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8101")),
    )
