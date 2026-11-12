from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from fastmcp import Client
from fastmcp.client.group import ClientGroup
from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool

TOOL_ALLOWLISTS: dict[str, frozenset[str]] = {
    "scout": frozenset({"search_jobs", "get_job"}),
    "risk_assessor": frozenset({"get_client_history"}),
    "fit_matcher": frozenset({"search_evidence", "get_case_study", "list_skills"}),
    "pricing": frozenset({"get_client_history", "get_connects_balance"}),
    "writer": frozenset({"search_evidence", "get_case_study"}),
    "critic": frozenset({"search_evidence", "get_case_study"}),
    "client_liaison": frozenset(
        {"list_messages", "list_free_slots", "create_tentative_hold", "create_email_draft"}
    ),
    "portfolio_builder": frozenset(
        {"get_file_contents", "search_code", "list_commits", "get_commit"}
    ),
}


@dataclass(frozen=True, slots=True)
class MCPConnectionSettings:
    portfolio_url: str = "http://portfolio-mcp:8101/mcp"
    marketplace_url: str = "http://marketplace-mcp:8102/mcp"
    workspace_url: str = "http://workspace-mcp:8103/mcp"
    upwork_url: str = "https://mcp.upwork.com/mcp"
    github_url: str = "https://api.githubcopilot.com/mcp/"
    bearer_token: str = ""
    upwork_access_token: str = ""
    github_access_token: str = ""


def build_mcp_client(settings: MCPConnectionSettings) -> MCPAdapter:
    """Build the maintained LangChain MCP adapter with server-prefixed tools."""

    owned_auth: str | None = settings.bearer_token or None
    clients = {
        "portfolio": Client(
            settings.portfolio_url,
            name="portfolio",
            auth=owned_auth,
            timeout=20,
        ),
        "marketplace": Client(
            settings.marketplace_url,
            name="marketplace",
            auth=owned_auth,
            timeout=20,
        ),
        "workspace": Client(
            settings.workspace_url,
            name="workspace",
            auth=owned_auth,
            timeout=20,
        ),
    }
    if settings.upwork_access_token:
        clients["upwork"] = Client(
            settings.upwork_url,
            name="upwork",
            auth=settings.upwork_access_token,
            timeout=30,
        )
    if settings.github_access_token:
        clients["github"] = Client(
            settings.github_url,
            name="github",
            auth=settings.github_access_token,
            timeout=30,
        )
    return MCPAdapter(ClientGroup(clients))


def allow_tools(agent_name: str, tools: Iterable[BaseTool]) -> list[BaseTool]:
    allowed = TOOL_ALLOWLISTS.get(agent_name, frozenset())
    return [
        tool
        for tool in tools
        if any(tool.name == name or tool.name.endswith(f"_{name}") for name in allowed)
    ]
