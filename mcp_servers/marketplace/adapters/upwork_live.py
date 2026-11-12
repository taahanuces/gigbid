from __future__ import annotations

from typing import Protocol

from agent.handoffs import DryRunPreview, MarketplaceReceipt


class ToolClient(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]: ...


class UpworkMCPAdapter:
    """Maps the official Upwork MCP surface onto the internal marketplace port."""

    def __init__(self, client: ToolClient) -> None:
        self.client = client

    async def search_jobs(self, *, tenant_id: str, query: str) -> list[dict[str, object]]:
        result = await self.client.call_tool("search_jobs", {"query": query})
        return _mapping_list(result.get("jobs"))

    async def get_job(self, *, tenant_id: str, job_id: str) -> dict[str, object]:
        return await self.client.call_tool("get_job", {"job_id": job_id})

    async def get_client_history(self, *, tenant_id: str, client_id: str) -> dict[str, object]:
        return await self.client.call_tool("get_client_history", {"client_id": client_id})

    async def get_connects_balance(self, *, tenant_id: str) -> int:
        result = await self.client.call_tool("get_connects_balance", {})
        return _required_int(result.get("balance"), field="balance")

    async def list_messages(
        self, *, tenant_id: str, conversation_id: str
    ) -> list[dict[str, object]]:
        result = await self.client.call_tool(
            "list_messages", {"conversation_id": conversation_id}
        )
        return _mapping_list(result.get("messages"))

    async def preview_proposal(
        self, *, tenant_id: str, payload: dict[str, object]
    ) -> DryRunPreview:
        return DryRunPreview(
            tool_name="create_proposal_draft",
            payload=payload,
            connects_cost=_required_int(
                payload.get("connects_cost", 0), field="connects_cost"
            ),
            side_effects=["Creates an Upwork draft; final confirmation remains on Upwork"],
        )

    async def create_proposal_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        result = await self.client.call_tool(
            "create_proposal_draft",
            {**payload, "idempotency_key": idempotency_key},
        )
        return MarketplaceReceipt.model_validate(result)

    async def submit_proposal(
        self,
        *,
        tenant_id: str,
        proposal_id: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        raise PermissionError(
            "Live mode creates drafts only; the user must confirm submission on Upwork."
        )

    async def send_message(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        body: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        result = await self.client.call_tool(
            "create_message_draft",
            {
                "conversation_id": conversation_id,
                "body": body,
                "idempotency_key": idempotency_key,
            },
        )
        return MarketplaceReceipt.model_validate(result)


def _mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("Expected a list from the Upwork MCP server")
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("Upwork MCP list contained a non-object item")
    return [{str(key): item for key, item in record.items()} for record in value]


def _required_int(value: object, *, field: str) -> int:
    if not isinstance(value, (str, int, float)):
        raise ValueError(f"Upwork MCP field {field!r} must be numeric")
    return int(value)
