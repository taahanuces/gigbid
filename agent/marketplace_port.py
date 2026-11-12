from __future__ import annotations

from typing import Protocol, runtime_checkable

from agent.handoffs import DryRunPreview, MarketplaceReceipt


@runtime_checkable
class MarketplacePort(Protocol):
    async def search_jobs(self, *, tenant_id: str, query: str) -> list[dict[str, object]]: ...

    async def get_job(self, *, tenant_id: str, job_id: str) -> dict[str, object]: ...

    async def get_client_history(self, *, tenant_id: str, client_id: str) -> dict[str, object]: ...

    async def get_connects_balance(self, *, tenant_id: str) -> int: ...

    async def list_messages(
        self, *, tenant_id: str, conversation_id: str
    ) -> list[dict[str, object]]: ...

    async def preview_proposal(
        self, *, tenant_id: str, payload: dict[str, object]
    ) -> DryRunPreview: ...

    async def create_proposal_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt: ...

    async def submit_proposal(
        self,
        *,
        tenant_id: str,
        proposal_id: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt: ...

    async def send_message(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        body: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt: ...
