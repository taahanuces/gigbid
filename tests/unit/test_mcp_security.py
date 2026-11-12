from langchain_core.tools import StructuredTool

from agent.mcp_client import allow_tools
from mcp_servers.auth import StaticBearerTokenVerifier


def _noop() -> str:
    """Return a deterministic marker."""

    return "ok"


async def test_static_bearer_verifier_rejects_wrong_token() -> None:
    verifier = StaticBearerTokenVerifier("correct-secret", "http://localhost:8102/mcp")
    assert await verifier.verify_token("wrong-secret") is None
    token = await verifier.verify_token("correct-secret")
    assert token is not None
    assert token.resource == "http://localhost:8102/mcp"


def test_agent_tool_allowlist_handles_server_prefixes() -> None:
    allowed = StructuredTool.from_function(_noop, name="portfolio_search_evidence")
    denied = StructuredTool.from_function(_noop, name="marketplace_submit_proposal")
    assert allow_tools("writer", [allowed, denied]) == [allowed]
