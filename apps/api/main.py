from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import RequestResponseEndpoint

from agent.observability import (
    API_LATENCY,
    API_REQUESTS,
    JsonTraceRecorder,
    Timer,
    normalize_trace_id,
    reset_trace_id,
    set_trace_id,
)
from agent.persistence import checkpoint_serializer, postgres_persistence
from agent.telemetry import configure_telemetry, trace_span
from apps.api.context import AppContext, build_context
from apps.api.routers import auth, conversations, jobs, memories, portfolio, product, profile, runs
from apps.api.schemas.api import HealthResponse

configure_telemetry()


def _cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "").strip()
    if configured:
        return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    if os.getenv("APP_ENV", "development").lower() == "production":
        return []
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    backend = os.getenv("CHECKPOINT_BACKEND", "memory")
    if backend == "postgres":
        database_url = os.environ["DATABASE_URL"]
        async with postgres_persistence(database_url) as (checkpointer, store):
            context = build_context(
                checkpointer=checkpointer,
                store=store,
                checkpoint_backend="postgres",
            )
            app.state.context = context
            try:
                yield
            finally:
                await _close_marketplace(context)
        return

    memory_store = InMemoryStore()
    context = build_context(
        checkpointer=InMemorySaver(serde=checkpoint_serializer()),
        store=memory_store,
        checkpoint_backend="memory",
    )
    app.state.context = context
    try:
        yield
    finally:
        await _close_marketplace(context)


async def _close_marketplace(context: AppContext) -> None:
    close = getattr(context.marketplace, "aclose", None)
    if callable(close):
        await close()


app = FastAPI(
    title="GigBid API",
    version="0.1.0",
    description="Human-controlled multi-agent freelancer copilot",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(memories.router, prefix="/api")
app.include_router(product.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
trace_recorder = JsonTraceRecorder()


@app.middleware("http")
async def observe_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    trace_id = normalize_trace_id(request.headers.get("X-Trace-ID"))
    token = set_trace_id(trace_id)
    timer = Timer()
    status_code = 500
    with trace_span(
        "http.request",
        {
            "gigbid.trace_id": trace_id,
            "http.request.method": request.method,
        },
    ) as span:
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            route_object = request.scope.get("route")
            route = getattr(route_object, "path", request.url.path)
            duration = timer.elapsed
            span.set_attribute("http.route", str(route))
            span.set_attribute("http.response.status_code", status_code)
            API_REQUESTS.labels(
                method=request.method,
                route=str(route),
                status=str(status_code),
            ).inc()
            API_LATENCY.labels(method=request.method, route=str(route)).observe(duration)
            trace_recorder.record_request(
                trace_id=trace_id,
                method=request.method,
                route=str(route),
                status_code=status_code,
                duration_seconds=duration,
            )
            reset_trace_id(token)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    mode = request.app.state.context.marketplace_mode
    marketplace = "available"
    if mode != "memory":
        endpoint = (
            f"{os.getenv('GIGSIM_BASE_URL', 'http://gigsim:8081').rstrip('/')}/health"
            if mode == "gigsim"
            else os.getenv("MARKETPLACE_MCP_URL", "http://marketplace-mcp:8102/mcp")
        )
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(endpoint)
            if response.status_code >= 500:
                marketplace = "unavailable"
        except httpx.HTTPError:
            marketplace = "unavailable"
    return HealthResponse(
        status="degraded" if marketplace == "unavailable" else "ok",
        service="gigbid-api",
        dependencies={
            "marketplace": marketplace,
            "checkpointer": request.app.state.context.checkpoint_backend,
        },
    )
