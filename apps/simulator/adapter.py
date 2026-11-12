from __future__ import annotations

from copy import deepcopy

from agent.handoffs import DryRunPreview, MarketplaceReceipt
from apps.simulator.engine import SimulatorState


class SimulatorMarketplaceAdapter:
    """In-process port adapter with the same semantics as the simulator REST API."""

    def __init__(self, state: SimulatorState) -> None:
        self.state = state

    async def search_jobs(self, *, tenant_id: str, query: str) -> list[dict[str, object]]:
        del tenant_id
        terms = query.lower().split()
        return [
            deepcopy(job)
            for job in self.state.jobs.values()
            if not terms or all(term in str(job).lower() for term in terms)
        ]

    async def get_job(self, *, tenant_id: str, job_id: str) -> dict[str, object]:
        del tenant_id
        return deepcopy(self.state.jobs[job_id])

    async def get_client_history(self, *, tenant_id: str, client_id: str) -> dict[str, object]:
        del tenant_id
        client = deepcopy(self.state.clients[client_id])
        client.pop("hidden_preferences", None)
        return client

    async def get_connects_balance(self, *, tenant_id: str) -> int:
        return self.state.balance(tenant_id)

    async def list_messages(
        self, *, tenant_id: str, conversation_id: str
    ) -> list[dict[str, object]]:
        del tenant_id
        return deepcopy(self.state.messages.get(conversation_id, []))

    async def preview_proposal(
        self, *, tenant_id: str, payload: dict[str, object]
    ) -> DryRunPreview:
        del tenant_id
        job = self.state.jobs[str(payload["job_id"])]
        raw_cost = job.get("connects_cost", 0)
        if not isinstance(raw_cost, (str, int, float)):
            raise ValueError("Job connects_cost must be numeric")
        cost = int(raw_cost)
        return DryRunPreview(
            tool_name="create_proposal_draft",
            payload=deepcopy(payload),
            connects_cost=cost,
            side_effects=["Creates a simulator proposal draft", f"Reserves {cost} Connects"],
        )

    async def create_proposal_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        return self.state.create_draft(
            tenant_id=tenant_id,
            payload=deepcopy(payload),
            idempotency_key=idempotency_key,
        )

    async def submit_proposal(
        self,
        *,
        tenant_id: str,
        proposal_id: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        return self.state.submit(
            tenant_id=tenant_id,
            proposal_id=proposal_id,
            idempotency_key=idempotency_key,
        )

    async def send_message(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        body: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        return self.state.send_message(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            body=body,
            idempotency_key=idempotency_key,
        )
