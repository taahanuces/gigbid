from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START
from langgraph.store.memory import InMemoryStore

from agent.persistence import checkpoint_serializer
from apps.api.context import build_context


async def test_seeded_run_resumes_from_durable_start_checkpoint() -> None:
    context = build_context(
        checkpointer=InMemorySaver(serde=checkpoint_serializer()),
        store=InMemoryStore(),
    )
    thread_id = "async-seed-test"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "thread_id": thread_id,
        "trace_id": "trace-async-seed",
        "tenant_id": "demo",
        "user_id": "reviewer-001",
        "job_id": "job-forecast-001",
        "user_floor": 300,
        "persona": "data-analyst",
        "max_connects_per_bid": 16,
        "weekly_connects_budget": 80,
        "status": "queued",
        "revision_count": 0,
        "step_count": 0,
        "token_count": 0,
        "events": [],
        "errors": [],
    }

    await context.graph.aupdate_state(config, initial_state, as_node=START)
    queued = await context.graph.aget_state(config)
    assert queued.values["status"] == "queued"
    assert queued.next == ("load_job",)

    await context.graph.ainvoke(None, config)
    resumed = await context.graph.aget_state(config)
    assert resumed.values["status"] == "awaiting_approval"
    assert resumed.values["trace_id"] == "trace-async-seed"
