import json
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.config import AppConfig, load_config
from agent.graphs.bid_graph import BidGraphServices, build_bid_graph
from agent.handoffs import EvidenceItem, MarketplaceReceipt
from agent.memory.store import LongTermMemory
from agent.persistence import checkpoint_serializer
from mcp_servers.marketplace.adapters.memory import InMemoryMarketplaceAdapter
from rag.index.memory import InMemoryEvidenceIndex

ROOT = Path(__file__).resolve().parents[2]


def make_graph(
    *,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    marketplace: InMemoryMarketplaceAdapter | None = None,
    store: BaseStore | None = None,
    app_config: AppConfig | None = None,
) -> tuple[Any, InMemoryMarketplaceAdapter]:
    jobs = json.loads((ROOT / "evals/datasets/smoke_jobs.json").read_text())
    evidence = [
        EvidenceItem.model_validate(item)
        for item in json.loads((ROOT / "evals/datasets/smoke_portfolio.json").read_text())
    ]
    marketplace = marketplace or InMemoryMarketplaceAdapter(jobs=jobs)
    graph = build_bid_graph(
        BidGraphServices(
            marketplace=marketplace,
            evidence_index=InMemoryEvidenceIndex(evidence),
            config=app_config or load_config(ROOT / "agent/config.yaml"),
            store=store,
        ),
        checkpointer=checkpointer,
    )
    return graph, marketplace


async def start_bid(graph: Any, thread_id: str) -> dict[str, dict[str, str]]:
    config = {"configurable": {"thread_id": thread_id}}
    await graph.ainvoke(
        {
            "thread_id": thread_id,
            "tenant_id": "demo",
            "user_id": "reviewer",
            "job_id": "job-forecast-001",
            "events": [],
            "errors": [],
            "revision_count": 0,
            "step_count": 0,
            "token_count": 0,
        },
        config,
    )
    return config


class CrashAfterWriteMarketplace(InMemoryMarketplaceAdapter):
    """Simulate process failure after an upstream service accepted the write."""

    def __init__(self, *, jobs: list[dict[str, object]]) -> None:
        super().__init__(jobs=jobs)
        self.fail_after_write = True

    async def create_proposal_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        receipt = await super().create_proposal_draft(
            tenant_id=tenant_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        if self.fail_after_write:
            self.fail_after_write = False
            raise RuntimeError("simulated crash after upstream write")
        return receipt


async def test_bid_graph_interrupts_then_writes_once() -> None:
    graph, marketplace = make_graph()
    config = await start_bid(graph, "thread-bid")
    pending = await graph.aget_state(config)
    assert pending.values["status"] == "awaiting_approval"
    assert marketplace.proposals == {}

    await graph.ainvoke(Command(resume={"action": "approve"}), config)
    complete = await graph.aget_state(config)
    assert complete.values["status"] == "draft_created"
    assert len(marketplace.proposals) == 1


async def test_bid_graph_resumes_after_graph_reconstruction() -> None:
    checkpointer = InMemorySaver(serde=checkpoint_serializer())
    graph_before_restart, marketplace = make_graph(checkpointer=checkpointer)
    config = await start_bid(graph_before_restart, "thread-restart")
    pending = await graph_before_restart.aget_state(config)
    assert pending.values["status"] == "awaiting_approval"

    graph_after_restart, _ = make_graph(
        checkpointer=checkpointer,
        marketplace=marketplace,
    )
    restored = await graph_after_restart.aget_state(config)
    assert restored.values["user_id"] == "reviewer"
    assert restored.values["tenant_id"] == "demo"

    await graph_after_restart.ainvoke(Command(resume={"action": "approve"}), config)
    complete = await graph_after_restart.aget_state(config)
    assert complete.values["status"] == "draft_created"
    assert len(marketplace.proposals) == 1


async def test_retry_after_post_write_crash_is_exactly_once() -> None:
    jobs = json.loads((ROOT / "evals/datasets/smoke_jobs.json").read_text())
    marketplace = CrashAfterWriteMarketplace(jobs=jobs)
    checkpointer = InMemorySaver(serde=checkpoint_serializer())
    graph, _ = make_graph(checkpointer=checkpointer, marketplace=marketplace)
    config = await start_bid(graph, "thread-post-write-crash")

    with pytest.raises(RuntimeError, match="after upstream write"):
        await graph.ainvoke(Command(resume={"action": "approve"}), config)
    assert len(marketplace.proposals) == 1
    assert len(marketplace.receipts) == 1

    restarted_graph, _ = make_graph(
        checkpointer=checkpointer,
        marketplace=marketplace,
    )
    await restarted_graph.ainvoke(None, config)
    complete = await restarted_graph.aget_state(config)
    assert complete.values["status"] == "draft_created"
    assert len(marketplace.proposals) == 1


async def test_step_budget_stops_before_marketplace_write() -> None:
    config = load_config(ROOT / "agent/config.yaml")
    limited = config.model_copy(
        update={"budgets": config.budgets.model_copy(update={"max_graph_steps": 5})}
    )
    graph, marketplace = make_graph(app_config=limited)
    thread = await start_bid(graph, "thread-budget")
    complete = await graph.aget_state(thread)
    assert complete.values["status"] == "needs_attention"
    assert complete.values["step_count"] == 6
    assert marketplace.proposals == {}


async def test_approved_edits_are_promoted_after_three_distinct_runs() -> None:
    store = InMemoryStore()
    graph, _ = make_graph(store=store)
    edited_text = "Your forecast will include:\n- a baseline\n- an error report"
    memory = LongTermMemory(store, tenant_id="demo", user_id="reviewer")
    for index in range(3):
        config = await start_bid(graph, f"thread-style-{index}")
        await graph.ainvoke(
            Command(
                resume={
                    "action": "edit",
                    "edited_cover_letter": edited_text,
                }
            ),
            config,
        )
        assert await memory.list_promoted() == []
        await graph.ainvoke(Command(resume={"action": "approve"}), config)

    promoted = await memory.list_promoted()
    assert promoted
    assert promoted[0].evidence_count == 3


async def test_risky_job_terminates_without_draft() -> None:
    graph, marketplace = make_graph()
    config = {"configurable": {"thread_id": "thread-risk"}}
    result = await graph.ainvoke(
        {
            "thread_id": "thread-risk",
            "tenant_id": "demo",
            "user_id": "reviewer",
            "job_id": "job-risk-002",
            "events": [],
            "errors": [],
            "revision_count": 0,
        },
        config,
    )
    assert result["status"] == "skip"
    assert marketplace.proposals == {}
