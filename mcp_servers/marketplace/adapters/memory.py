from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from agent.handoffs import DryRunPreview, MarketplaceReceipt


class InMemoryMarketplaceAdapter:
    """Deterministic adapter used for tests and the local demo."""

    def __init__(
        self,
        *,
        jobs: list[dict[str, object]] | None = None,
        clients: dict[str, dict[str, object]] | None = None,
        connects: int = 100,
    ) -> None:
        self.jobs = {str(job["job_id"]): deepcopy(job) for job in jobs or []}
        self.clients = deepcopy(clients or {})
        self.connects = connects
        self.messages: dict[str, list[dict[str, object]]] = {}
        self.receipts: dict[str, MarketplaceReceipt] = {}
        self.proposals: dict[str, dict[str, object]] = {}

    async def search_jobs(self, *, tenant_id: str, query: str) -> list[dict[str, object]]:
        terms = query.lower().split()
        return [
            deepcopy(job)
            for job in self.jobs.values()
            if not terms or any(term in str(job).lower() for term in terms)
        ]

    async def get_job(self, *, tenant_id: str, job_id: str) -> dict[str, object]:
        if job_id not in self.jobs:
            raise KeyError(f"Unknown job: {job_id}")
        return deepcopy(self.jobs[job_id])

    async def get_client_history(self, *, tenant_id: str, client_id: str) -> dict[str, object]:
        return deepcopy(
            self.clients.get(
                client_id,
                {
                    "client_id": client_id,
                    "payment_verified": True,
                    "average_rating": 4.0,
                    "completed_projects": 1,
                },
            )
        )

    async def get_connects_balance(self, *, tenant_id: str) -> int:
        return self.connects

    async def list_messages(
        self, *, tenant_id: str, conversation_id: str
    ) -> list[dict[str, object]]:
        return deepcopy(self.messages.get(conversation_id, []))

    async def preview_proposal(
        self, *, tenant_id: str, payload: dict[str, object]
    ) -> DryRunPreview:
        job = self.jobs.get(str(payload.get("job_id")), {})
        raw_cost = job.get("connects_cost", 0)
        cost = int(raw_cost) if isinstance(raw_cost, (str, int, float)) else 0
        return DryRunPreview(
            tool_name="create_proposal_draft",
            payload=deepcopy(payload),
            connects_cost=cost,
            side_effects=["Creates a marketplace proposal draft", f"Reserves {cost} Connects"],
        )

    async def create_proposal_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        existing = self.receipts.get(idempotency_key)
        if existing:
            return existing
        preview = await self.preview_proposal(tenant_id=tenant_id, payload=payload)
        if preview.connects_cost > self.connects:
            raise ValueError("Insufficient Connects")
        proposal_id = f"proposal-{uuid4()}"
        self.connects -= preview.connects_cost
        self.proposals[proposal_id] = deepcopy(payload)
        receipt = MarketplaceReceipt(
            marketplace_id=proposal_id,
            action="create_proposal_draft",
            status="draft_created",
            idempotency_key=idempotency_key,
            connects_spent=preview.connects_cost,
        )
        self.receipts[idempotency_key] = receipt
        return receipt

    async def submit_proposal(
        self,
        *,
        tenant_id: str,
        proposal_id: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        existing = self.receipts.get(idempotency_key)
        if existing:
            return existing
        if proposal_id not in self.proposals:
            raise KeyError(f"Unknown proposal: {proposal_id}")
        receipt = MarketplaceReceipt(
            marketplace_id=proposal_id,
            action="submit_proposal",
            status="submitted",
            idempotency_key=idempotency_key,
        )
        self.receipts[idempotency_key] = receipt
        return receipt

    async def send_message(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        body: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        existing = self.receipts.get(idempotency_key)
        if existing:
            return existing
        message_id = f"message-{uuid4()}"
        self.messages.setdefault(conversation_id, []).append(
            {"message_id": message_id, "direction": "outbound", "body": body}
        )
        receipt = MarketplaceReceipt(
            marketplace_id=message_id,
            action="send_message",
            status="sent",
            idempotency_key=idempotency_key,
        )
        self.receipts[idempotency_key] = receipt
        return receipt
