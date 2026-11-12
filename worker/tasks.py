from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol, cast
from uuid import uuid4

from celery.signals import task_failure
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from agent.observability import record_graph_run
from agent.persistence import postgres_persistence
from agent.security import redact_pii
from agent.state import GigBidState
from agent.telemetry import configure_telemetry, trace_span
from apps.api.context import build_context
from apps.api.portfolio_store import list_uploaded_evidence
from apps.api.profile_store import load_profile
from apps.api.run_store import save_run_summary
from worker.celery_app import REDIS_URL, celery_app

LOGGER = logging.getLogger(__name__)
configure_telemetry()
JOB_EVENT_CHANNEL = "gigbid:runs"
DEFAULT_DEAD_LETTER_KEY = "gigbid:dead-letter"
ENQUEUE_JOB_SCRIPT = """
local created = redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2])
if not created then
  return 0
end
redis.call('PUBLISH', ARGV[3], ARGV[4])
return 1
"""


class RedisScriptClient(Protocol):
    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object: ...


class RedisDeadLetterClient(Protocol):
    def lpush(self, key: str, value: str) -> object: ...

    def ltrim(self, key: str, start: int, end: int) -> object: ...

    def expire(self, key: str, seconds: int) -> object: ...


def _job_key(tenant_id: str, job_id: str, thread_id: str | None = None) -> str:
    digest = hashlib.sha256(f"{tenant_id}:{job_id}:{thread_id or ''}".encode()).hexdigest()
    return f"gigbid:job-lock:{digest}"


def _bounded_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def enqueue_job_once(
    redis: RedisScriptClient,
    *,
    tenant_id: str,
    job_id: str,
    trace_id: str | None = None,
    thread_id: str | None = None,
) -> bool:
    payload = {
        "tenant_id": tenant_id,
        "job_id": job_id,
        "status": "queued_for_graph",
        "trace_id": trace_id,
        "thread_id": thread_id,
    }
    result = redis.eval(
        ENQUEUE_JOB_SCRIPT,
        1,
        _job_key(tenant_id, job_id, thread_id),
        "processing",
        60 * 30,
        JOB_EVENT_CHANNEL,
        json.dumps(payload, sort_keys=True),
    )
    return cast(int, result) == 1


def dead_letter_payload(
    *,
    task_name: str,
    task_id: str | None,
    exception: BaseException | None,
    args: tuple[object, ...] | None,
    kwargs: dict[str, object] | None,
) -> dict[str, object]:
    safe_args = redact_pii(json.dumps(args or (), default=str))[:2_000]
    safe_kwargs = redact_pii(json.dumps(kwargs or {}, default=str, sort_keys=True))[:2_000]
    error_message = redact_pii(str(exception or "unknown failure"))[:1_000]
    return {
        "failed_at": datetime.now(UTC).isoformat(),
        "task_name": task_name,
        "task_id": task_id,
        "exception_type": type(exception).__name__ if exception else "UnknownError",
        "error": error_message,
        "args": safe_args,
        "kwargs": safe_kwargs,
    }


def record_dead_letter(
    payload: dict[str, object], redis: RedisDeadLetterClient | None = None
) -> None:
    client = redis or Redis.from_url(REDIS_URL, decode_responses=True)
    key = os.getenv("DEAD_LETTER_KEY", DEFAULT_DEAD_LETTER_KEY)
    maximum = _bounded_env_int("DEAD_LETTER_MAX", 1_000, minimum=10, maximum=100_000)
    retention_seconds = _bounded_env_int(
        "DEAD_LETTER_RETENTION_SECONDS",
        14 * 24 * 60 * 60,
        minimum=60,
        maximum=90 * 24 * 60 * 60,
    )
    serialized = json.dumps(payload, sort_keys=True)
    client.lpush(key, serialized)
    client.ltrim(key, 0, maximum - 1)
    client.expire(key, retention_seconds)


@task_failure.connect  # type: ignore[untyped-decorator]
def capture_terminal_failure(
    sender: object | None = None,
    task_id: str | None = None,
    exception: BaseException | None = None,
    args: tuple[object, ...] | None = None,
    kwargs: dict[str, object] | None = None,
    **_: object,
) -> None:
    task_name = str(getattr(sender, "name", "unknown"))
    if not task_name.startswith("gigbid."):
        return
    payload = dead_letter_payload(
        task_name=task_name,
        task_id=task_id,
        exception=exception,
        args=args,
        kwargs=kwargs,
    )
    try:
        record_dead_letter(payload)
    except RedisError as error:
        LOGGER.error("Could not persist dead-letter event: %s", type(error).__name__)


async def execute_bid_graph(
    *,
    tenant_id: str,
    user_id: str,
    job_id: str,
    thread_id: str,
) -> dict[str, str]:
    database_url = os.environ["DATABASE_URL"]
    started = perf_counter()
    async with postgres_persistence(database_url) as (checkpointer, store):
        context = build_context(
            checkpointer=checkpointer,
            store=store,
            checkpoint_backend="postgres",
        )
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        try:
            snapshot = await context.graph.aget_state(config)
            state = snapshot.values
            if (
                state.get("tenant_id") != tenant_id
                or state.get("user_id") != user_id
                or state.get("job_id") != job_id
            ):
                raise ValueError("Queued run identity does not match its durable checkpoint")
            with trace_span(
                "gigbid.bid_graph.worker",
                {
                    "gigbid.trace_id": str(state.get("trace_id") or ""),
                    "gigbid.thread_id": thread_id,
                    "gigbid.graph": "bid",
                },
            ):
                await context.graph.ainvoke(None, config)
            completed = await context.graph.aget_state(config)
            status = str(completed.values.get("status", "unknown"))
            await save_run_summary(store, dict(completed.values))
            record_graph_run(status=status, duration_seconds=perf_counter() - started)
            return {"status": status, "job_id": job_id, "thread_id": thread_id}
        finally:
            close = getattr(context.marketplace, "aclose", None)
            if callable(close):
                await close()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="gigbid.analyze_job",
    autoretry_for=(ConnectionError, TimeoutError, RedisConnectionError, RedisTimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def analyze_job_task(
    tenant_id: str,
    user_id: str,
    job_id: str,
    thread_id: str,
    trace_id: str | None = None,
) -> dict[str, str]:
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    if not enqueue_job_once(
        cast(RedisScriptClient, redis),
        tenant_id=tenant_id,
        job_id=job_id,
        trace_id=trace_id,
        thread_id=thread_id,
    ):
        return {"status": "duplicate_suppressed", "job_id": job_id, "thread_id": thread_id}
    result = asyncio.run(
        execute_bid_graph(
            tenant_id=tenant_id,
            user_id=user_id,
            job_id=job_id,
            thread_id=thread_id,
        )
    )
    redis.publish(
        JOB_EVENT_CHANNEL,
        json.dumps({**result, "tenant_id": tenant_id, "trace_id": trace_id}, sort_keys=True),
    )
    return result


@celery_app.task(name="gigbid.scout_saved_searches")  # type: ignore[untyped-decorator]
def scout_saved_searches() -> dict[str, str]:
    return asyncio.run(execute_saved_searches())


async def execute_saved_searches() -> dict[str, str]:
    database_url = os.environ["DATABASE_URL"]
    tenant_id = os.getenv("SCOUT_TENANT_ID", "demo")
    user_id = os.getenv("SCOUT_USER_ID", "reviewer-001")
    queued = 0
    duplicates = 0
    async with postgres_persistence(database_url) as (checkpointer, store):
        context = build_context(
            checkpointer=checkpointer,
            store=store,
            checkpoint_backend="postgres",
        )
        try:
            profile = await load_profile(store, tenant_id=tenant_id, user_id=user_id)
            base_evidence = context.evidence_indexes.get(
                profile.persona, context.evidence_index
            ).all()
            uploaded_evidence = await list_uploaded_evidence(
                store,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            jobs = await context.marketplace.search_jobs(
                tenant_id=tenant_id,
                query=" ".join(profile.search_keywords),
            )
            namespace = ("gigbid", tenant_id, user_id, "scout", "seen")
            for job in jobs[:20]:
                job_id = str(job["job_id"])
                if await store.aget(namespace, job_id) is not None:
                    duplicates += 1
                    continue
                thread_id = str(uuid4())
                trace_id = uuid4().hex
                config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
                initial_state: GigBidState = {
                    "trace_id": trace_id,
                    "thread_id": thread_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "user_floor": profile.fixed_price_floor,
                    "persona": profile.persona,
                    "portfolio_evidence": [
                        item
                        for item in [*base_evidence, *uploaded_evidence]
                        if item.persona == profile.persona
                    ],
                    "max_connects_per_bid": profile.max_connects_per_bid,
                    "weekly_connects_budget": profile.weekly_connects_budget,
                    "job_id": job_id,
                    "status": "queued",
                    "revision_count": 0,
                    "step_count": 0,
                    "token_count": 0,
                    "model_usage": [],
                    "events": [],
                    "errors": [],
                }
                await context.graph.aupdate_state(config, initial_state, as_node=START)
                analyze_job_task.delay(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    job_id=job_id,
                    thread_id=thread_id,
                    trace_id=trace_id,
                )
                await store.aput(
                    namespace,
                    job_id,
                    {
                        "thread_id": thread_id,
                        "queued_at": datetime.now(UTC).isoformat(),
                    },
                    index=False,
                )
                queued += 1
        finally:
            close = getattr(context.marketplace, "aclose", None)
            if callable(close):
                await close()
    return {
        "status": "complete",
        "queued": str(queued),
        "duplicates": str(duplicates),
    }
