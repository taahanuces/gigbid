from __future__ import annotations

import os
from pathlib import Path

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from agent.handoffs import DryRunPreview
from agent.marketplace_port import MarketplacePort
from mcp_servers.audit import AppendOnlyAuditLog
from mcp_servers.auth import bearer_auth
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter, PerTenantRateLimiter
from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter
from mcp_servers.marketplace.schemas import (
    ClientHistoryInput,
    ConnectsInput,
    ConnectsResult,
    GetJobInput,
    JobSearchResult,
    MessagesInput,
    MessagesResult,
    ProposalActionResult,
    ProposalDraftInput,
    SearchJobsInput,
    SendMessageInput,
    SubmitProposalInput,
)


def _configured_port() -> MarketplacePort:
    mode = os.getenv("MARKETPLACE_MODE", "memory")
    if mode == "memory":
        return InMemoryMarketplaceAdapter()
    if mode == "gigsim":
        return GigSimAdapter(
            base_url=os.environ["GIGSIM_BASE_URL"],
            api_token=os.environ["GIGSIM_API_TOKEN"],
            requests_per_minute=int(os.getenv("GIGSIM_REQUESTS_PER_MINUTE", "18")),
        )
    raise ValueError(f"Marketplace MCP supports memory or gigsim mode, received: {mode}")


def _result_dict(result: object) -> dict[str, object]:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, dict):
        return result
    return {"value": result}


def build_server(port: MarketplacePort | None = None) -> MCPServer:
    marketplace = port or _configured_port()
    resource_url = os.getenv("MCP_RESOURCE_URL", "http://localhost:8102/mcp")
    token_verifier, auth = bearer_auth(resource_url)
    server = MCPServer(
        "gigbid-marketplace",
        token_verifier=token_verifier,
        auth=auth,
    )
    limiter = PerTenantRateLimiter(int(os.getenv("MCP_REQUESTS_PER_MINUTE", "18")))
    audit_path = os.getenv("MCP_AUDIT_LOG", "").strip()
    audit = AppendOnlyAuditLog(Path(audit_path)) if audit_path else None

    def record(tool: str, input: BaseModel, result: object) -> None:
        if audit is None:
            return
        values = input.model_dump(mode="json")
        tenant_id = str(values.pop("tenant_id"))
        trace_id = str(values.pop("trace_id"))
        audit.record(
            user_id=tenant_id,
            tool=tool,
            arguments=values,
            result=_result_dict(result),
            trace_id=trace_id,
        )

    read = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=True,
    )
    additive_write = ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=True,
    )
    destructive_write = ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=True,
        open_world_hint=True,
    )

    @server.tool(annotations=read)
    async def search_jobs(input: SearchJobsInput) -> JobSearchResult:
        """Search marketplace jobs through the configured adapter."""
        await limiter.acquire(input.tenant_id)
        jobs = await marketplace.search_jobs(tenant_id=input.tenant_id, query=input.query)
        result = JobSearchResult(jobs=jobs)
        record("search_jobs", input, result)
        return result

    @server.tool(annotations=read)
    async def get_job(input: GetJobInput) -> dict[str, object]:
        """Load a complete marketplace job."""
        await limiter.acquire(input.tenant_id)
        result = await marketplace.get_job(tenant_id=input.tenant_id, job_id=input.job_id)
        record("get_job", input, result)
        return result

    @server.tool(annotations=read)
    async def get_client_history(input: ClientHistoryInput) -> dict[str, object]:
        """Load the marketplace history used for client-risk analysis."""
        await limiter.acquire(input.tenant_id)
        result = await marketplace.get_client_history(
            tenant_id=input.tenant_id, client_id=input.client_id
        )
        record("get_client_history", input, result)
        return result

    @server.tool(annotations=read)
    async def get_connects_balance(input: ConnectsInput) -> ConnectsResult:
        """Return the current Connects balance."""
        await limiter.acquire(input.tenant_id)
        result = ConnectsResult(
            balance=await marketplace.get_connects_balance(tenant_id=input.tenant_id)
        )
        record("get_connects_balance", input, result)
        return result

    @server.tool(annotations=read)
    async def list_messages(input: MessagesInput) -> MessagesResult:
        """List messages in one marketplace conversation."""
        await limiter.acquire(input.tenant_id)
        messages = await marketplace.list_messages(
            tenant_id=input.tenant_id, conversation_id=input.conversation_id
        )
        result = MessagesResult(messages=messages)
        record("list_messages", input, result)
        return result

    @server.tool(annotations=additive_write)
    async def create_proposal_draft(input: ProposalDraftInput) -> ProposalActionResult:
        """Preview or create one proposal draft after approval."""
        await limiter.acquire(input.tenant_id)
        payload = input.model_dump(exclude={"tenant_id", "trace_id", "idempotency_key", "dry_run"})
        if input.dry_run:
            result = ProposalActionResult(
                preview=await marketplace.preview_proposal(
                    tenant_id=input.tenant_id, payload=payload
                )
            )
        else:
            receipt = await marketplace.create_proposal_draft(
                tenant_id=input.tenant_id,
                payload=payload,
                idempotency_key=input.idempotency_key,
            )
            result = ProposalActionResult(receipt=receipt)
        record("create_proposal_draft", input, result)
        return result

    @server.tool(annotations=destructive_write)
    async def submit_proposal(input: SubmitProposalInput) -> ProposalActionResult:
        """Preview or submit a simulator proposal; live mode never uses this tool."""
        await limiter.acquire(input.tenant_id)
        if input.dry_run:
            result = ProposalActionResult(
                preview=DryRunPreview(
                    tool_name="submit_proposal",
                    payload={"proposal_id": input.proposal_id},
                    connects_cost=0,
                    side_effects=["Submits the proposal in GigSim"],
                )
            )
        else:
            result = ProposalActionResult(
                receipt=await marketplace.submit_proposal(
                    tenant_id=input.tenant_id,
                    proposal_id=input.proposal_id,
                    idempotency_key=input.idempotency_key,
                )
            )
        record("submit_proposal", input, result)
        return result

    @server.tool(annotations=destructive_write)
    async def send_message(input: SendMessageInput) -> ProposalActionResult:
        """Preview or send an approved marketplace message."""
        await limiter.acquire(input.tenant_id)
        if input.dry_run:
            result = ProposalActionResult(
                preview=DryRunPreview(
                    tool_name="send_message",
                    payload={"conversation_id": input.conversation_id, "body": input.body},
                    connects_cost=0,
                    side_effects=["Sends a message to the client"],
                )
            )
        else:
            result = ProposalActionResult(
                receipt=await marketplace.send_message(
                    tenant_id=input.tenant_id,
                    conversation_id=input.conversation_id,
                    body=input.body,
                    idempotency_key=input.idempotency_key,
                )
            )
        record("send_message", input, result)
        return result

    return server


mcp = build_server()


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8102")),
    )
