from __future__ import annotations

from langgraph.store.base import BaseStore

from agent.handoffs import EvidenceItem
from apps.api.profile_store import _label


def portfolio_namespace(tenant_id: str, user_id: str) -> tuple[str, ...]:
    return ("gigbid", _label(tenant_id), _label(user_id), "portfolio")


async def list_uploaded_evidence(
    store: BaseStore | None,
    *,
    tenant_id: str,
    user_id: str,
    limit: int = 1_000,
) -> list[EvidenceItem]:
    if store is None:
        return []
    items = await store.asearch(portfolio_namespace(tenant_id, user_id), limit=limit)
    return [EvidenceItem.model_validate(item.value) for item in items]


async def save_uploaded_evidence(
    store: BaseStore,
    *,
    tenant_id: str,
    user_id: str,
    items: list[EvidenceItem],
) -> list[EvidenceItem]:
    namespace = portfolio_namespace(tenant_id, user_id)
    for item in items:
        await store.aput(
            namespace,
            item.evidence_id,
            item.model_dump(mode="json"),
            index=False,
        )
    return items


async def delete_uploaded_evidence(
    store: BaseStore,
    *,
    tenant_id: str,
    user_id: str,
    evidence_id: str,
) -> None:
    await store.adelete(portfolio_namespace(tenant_id, user_id), evidence_id)
