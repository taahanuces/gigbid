from __future__ import annotations

import os
from datetime import datetime, timedelta
from uuid import uuid4

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from mcp_servers.auth import bearer_auth


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SlotQuery(WorkspaceInput):
    tenant_id: str
    start: datetime
    end: datetime
    timezone: str = "Asia/Karachi"
    limit: int = Field(default=5, ge=1, le=20)


class HoldInput(WorkspaceInput):
    tenant_id: str
    starts_at: datetime
    ends_at: datetime
    title: str = Field(min_length=3, max_length=200)
    idempotency_key: str = Field(min_length=8)
    dry_run: bool = True


class EmailDraftInput(WorkspaceInput):
    tenant_id: str
    recipient: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    idempotency_key: str = Field(min_length=8)
    dry_run: bool = True


class WorkspaceResult(BaseModel):
    status: str
    object_id: str | None = None
    preview: dict[str, object] | None = None


class LocalWorkspaceStore:
    def __init__(self) -> None:
        self.holds: dict[str, WorkspaceResult] = {}
        self.drafts: dict[str, WorkspaceResult] = {}


def build_server(store: LocalWorkspaceStore | None = None) -> MCPServer:
    workspace = store or LocalWorkspaceStore()
    resource_url = os.getenv("MCP_RESOURCE_URL", "http://localhost:8103/mcp")
    token_verifier, auth = bearer_auth(resource_url)
    server = MCPServer(
        "gigbid-workspace",
        token_verifier=token_verifier,
        auth=auth,
    )
    read = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    )
    write = ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    )

    @server.tool(annotations=read)
    def list_free_slots(input: SlotQuery) -> list[str]:
        """Return deterministic local-mock interview slots in ISO format."""
        if input.end <= input.start:
            raise ValueError("end must be later than start")
        current = input.start.replace(minute=0, second=0, microsecond=0)
        slots: list[str] = []
        while current < input.end and len(slots) < input.limit:
            if 9 <= current.hour < 17 and current.weekday() < 5:
                slots.append(current.isoformat())
            current += timedelta(hours=1)
        return slots

    @server.tool(annotations=write)
    def create_tentative_hold(input: HoldInput) -> WorkspaceResult:
        """Preview or create an idempotent tentative local calendar hold."""
        preview = {
            "starts_at": input.starts_at.isoformat(),
            "ends_at": input.ends_at.isoformat(),
            "title": input.title,
        }
        if input.dry_run:
            return WorkspaceResult(status="dry_run", preview=preview)
        if input.idempotency_key not in workspace.holds:
            workspace.holds[input.idempotency_key] = WorkspaceResult(
                status="tentative", object_id=f"hold-{uuid4()}", preview=preview
            )
        return workspace.holds[input.idempotency_key]

    @server.tool(annotations=write)
    def create_email_draft(input: EmailDraftInput) -> WorkspaceResult:
        """Preview or create an idempotent local email draft; it never sends mail."""
        preview = {"recipient": input.recipient, "subject": input.subject, "body": input.body}
        if input.dry_run:
            return WorkspaceResult(status="dry_run", preview=preview)
        if input.idempotency_key not in workspace.drafts:
            workspace.drafts[input.idempotency_key] = WorkspaceResult(
                status="draft", object_id=f"email-{uuid4()}", preview=preview
            )
        return workspace.drafts[input.idempotency_key]

    return server


mcp = build_server()


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8103")),
    )
