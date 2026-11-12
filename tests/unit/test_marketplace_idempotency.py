from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter


async def test_create_draft_is_idempotent() -> None:
    adapter = InMemoryMarketplaceAdapter(jobs=[{"job_id": "j1", "connects_cost": 4}], connects=20)
    payload = {"job_id": "j1", "cover_letter": "A sufficiently long grounded proposal."}
    first = await adapter.create_proposal_draft(
        tenant_id="demo", payload=payload, idempotency_key="same-key-123"
    )
    second = await adapter.create_proposal_draft(
        tenant_id="demo", payload=payload, idempotency_key="same-key-123"
    )
    assert first == second
    assert adapter.connects == 16
