from langgraph.store.memory import InMemoryStore

from agent.memory.promotion_rules import OutcomeObservation
from agent.memory.store import LongTermMemory, infer_style_patterns


def make_memory(
    store: InMemoryStore, *, tenant_id: str = "tenant-a", user_id: str = "user-a"
) -> LongTermMemory:
    return LongTermMemory(
        store,
        tenant_id=tenant_id,
        user_id=user_id,
        style_minimum_consistent_edits=3,
        outcome_minimum_observations=5,
        outcome_minimum_reply_rate=0.3,
    )


async def test_style_memory_is_promoted_only_after_three_distinct_edits() -> None:
    store = InMemoryStore()
    memory = make_memory(store)
    assert (
        await memory.record_style_observation(
            thread_id="thread-1", pattern="prefer_concise_proposals"
        )
        is None
    )
    await memory.record_style_observation(
        thread_id="thread-1", pattern="prefer_concise_proposals"
    )
    assert (
        await memory.record_style_observation(
            thread_id="thread-2", pattern="prefer_concise_proposals"
        )
        is None
    )
    promoted = await memory.record_style_observation(
        thread_id="thread-3", pattern="prefer_concise_proposals"
    )
    assert promoted is not None
    assert promoted.evidence_count == 3
    assert [item.value for item in await memory.list_promoted()] == [
        "prefer_concise_proposals"
    ]


async def test_memory_is_tenant_scoped_and_deletable() -> None:
    store = InMemoryStore()
    tenant_a = make_memory(store, tenant_id="tenant-a")
    tenant_b = make_memory(store, tenant_id="tenant-b")
    promoted = None
    for index in range(3):
        promoted = await tenant_a.record_style_observation(
            thread_id=f"thread-{index}", pattern="avoid_generic_openings"
        )
    assert promoted is not None
    assert await tenant_b.list_promoted() == []
    await tenant_a.delete_promoted("style", promoted.key)
    assert await tenant_a.list_promoted() == []


async def test_outcome_strategy_is_promoted_per_category() -> None:
    store = InMemoryStore()
    memory = make_memory(store)
    promoted = None
    for index in range(5):
        promoted = await memory.record_outcome(
            OutcomeObservation(
                job_id=f"job-{index}",
                category="data",
                strategy="lead-with-metric",
                replied=index < 3,
            )
        )
    assert promoted is not None
    assert promoted.category == "data"
    assert promoted.evidence_count == 5


def test_style_pattern_inference_is_inspectable() -> None:
    original = (
        "Hello, I am excited to help with this project. I have extensive experience and "
        "I can provide several detailed examples of my background."
    )
    edited = "Your forecast will include:\n- a baseline\n- an error report"
    patterns = infer_style_patterns(original, edited)
    assert "prefer_concise_proposals" in patterns
    assert "avoid_generic_openings" in patterns
    assert "prefer_bulleted_structure" in patterns
    assert "prefer_client_focused_language" in patterns
