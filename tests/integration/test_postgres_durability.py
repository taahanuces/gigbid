import os
from uuid import uuid4

import pytest
from langgraph.types import Command

from agent.persistence import postgres_persistence
from apps.api.context import build_context

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason="Set TEST_POSTGRES_URL to run the real Postgres restart test",
)
async def test_postgres_checkpoint_survives_connection_restart() -> None:
    assert POSTGRES_URL is not None
    thread_id = f"postgres-restart-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    async with postgres_persistence(POSTGRES_URL) as (checkpointer, store):
        before = build_context(
            checkpointer=checkpointer,
            store=store,
            checkpoint_backend="postgres",
        )
        await before.graph.ainvoke(
            {
                "thread_id": thread_id,
                "tenant_id": "demo",
                "user_id": "reviewer-001",
                "job_id": "job-forecast-001",
                "revision_count": 0,
                "step_count": 0,
                "token_count": 0,
                "events": [],
                "errors": [],
                "style_edit_patterns": [],
            },
            config,
        )
        pending = await before.graph.aget_state(config)
        assert pending.values["status"] == "awaiting_approval"

    async with postgres_persistence(POSTGRES_URL) as (checkpointer, store):
        after = build_context(
            checkpointer=checkpointer,
            store=store,
            checkpoint_backend="postgres",
        )
        restored = await after.graph.aget_state(config)
        assert restored.values["tenant_id"] == "demo"
        assert restored.values["status"] == "awaiting_approval"
        await after.graph.ainvoke(Command(resume={"action": "approve"}), config)
        complete = await after.graph.aget_state(config)
        assert complete.values["status"] == "draft_created"
