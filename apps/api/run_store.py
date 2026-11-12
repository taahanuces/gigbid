from __future__ import annotations

from typing import Any

from langgraph.store.base import BaseStore

from apps.api.profile_store import _label


def run_summary_namespace(tenant_id: str, user_id: str) -> tuple[str, ...]:
    return ("gigbid", _label(tenant_id), _label(user_id), "run_summaries")


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _number(value: object) -> float:
    return float(value) if isinstance(value, (str, int, float)) else 0.0


async def save_run_summary(store: BaseStore | None, state: dict[str, Any]) -> None:
    if store is None or not state.get("job_id"):
        return
    tenant_id = str(state["tenant_id"])
    user_id = str(state["user_id"])
    decision = state.get("decision")
    action = _field(decision, "action", state.get("status", "pending"))
    reasons = _field(decision, "reasons", [])
    await store.aput(
        run_summary_namespace(tenant_id, user_id),
        str(state["job_id"]),
        {
            "thread_id": str(state.get("thread_id", "")),
            "job_id": str(state["job_id"]),
            "status": str(state.get("status", "unknown")),
            "action": str(getattr(action, "value", action)),
            "fit_score": _number(_field(state.get("fit_report"), "score", 0)),
            "risk_score": _number(_field(state.get("risk_report"), "score", 0)),
            "recommended_price": (
                _number(_field(state.get("price_quote"), "amount"))
                if state.get("price_quote") is not None
                else None
            ),
            "reasons": [str(item) for item in reasons] if isinstance(reasons, list) else [],
        },
        index=False,
    )


async def list_run_summaries(
    store: BaseStore | None,
    *,
    tenant_id: str,
    user_id: str,
) -> dict[str, dict[str, object]]:
    if store is None:
        return {}
    items = await store.asearch(run_summary_namespace(tenant_id, user_id), limit=5_000)
    return {str(item.value["job_id"]): dict(item.value) for item in items}
