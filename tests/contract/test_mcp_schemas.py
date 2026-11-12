import hashlib
import json
from pathlib import Path

from mcp_servers.marketplace.server import build_server as build_marketplace
from mcp_servers.portfolio.server import build_server as build_portfolio
from mcp_servers.workspace.server import build_server as build_workspace


async def test_expected_tool_names_are_stable() -> None:
    portfolio = {tool.name for tool in await build_portfolio().list_tools()}
    marketplace = {tool.name for tool in await build_marketplace().list_tools()}
    workspace = {tool.name for tool in await build_workspace().list_tools()}
    assert portfolio == {"search_evidence", "get_case_study", "list_skills"}
    assert marketplace == {
        "search_jobs",
        "get_job",
        "get_client_history",
        "get_connects_balance",
        "list_messages",
        "create_proposal_draft",
        "submit_proposal",
        "send_message",
    }
    assert workspace == {"list_free_slots", "create_tentative_hold", "create_email_draft"}


async def test_full_tool_schemas_match_reviewed_snapshots() -> None:
    servers = {
        "portfolio": build_portfolio(),
        "marketplace": build_marketplace(),
        "workspace": build_workspace(),
    }
    snapshot_path = Path(__file__).parent / "snapshots/mcp_tools.json"
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    actual: dict[str, str] = {}
    for name, server in servers.items():
        schemas = [tool.model_dump(mode="json") for tool in await server.list_tools()]
        canonical = json.dumps(schemas, sort_keys=True, separators=(",", ":"))
        actual[name] = hashlib.sha256(canonical.encode()).hexdigest()
    assert actual == expected, "MCP schema changed; inspect it and update the reviewed snapshot"
