from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.store.postgres.aio import AsyncPostgresStore

from agent import handoffs
from agent.nodes.client_liaison import LiaisonDraft


def checkpoint_serializer(*extra_types: type[object]) -> JsonPlusSerializer:
    """Allow only GigBid's reviewed hand-off classes beyond LangGraph's safe built-ins."""

    handoff_types = tuple(
        value
        for value in vars(handoffs).values()
        if isinstance(value, type) and value.__module__ == handoffs.__name__
    )
    return JsonPlusSerializer(allowed_msgpack_modules=(*handoff_types, LiaisonDraft, *extra_types))


@asynccontextmanager
async def postgres_persistence(
    database_url: str,
) -> AsyncIterator[tuple[AsyncPostgresSaver, AsyncPostgresStore]]:
    checkpoint_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    async with AsyncPostgresSaver.from_conn_string(
        checkpoint_url,
        serde=checkpoint_serializer(),
    ) as checkpointer:
        async with AsyncPostgresStore.from_conn_string(checkpoint_url) as store:
            await checkpointer.setup()
            await store.setup()
            yield checkpointer, store
