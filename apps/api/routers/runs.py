from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from agent.handoffs import EvidenceItem, JobSpec, PriceQuote, ProposalDraft
from agent.nodes.paragraph_reviser import regenerate_paragraph
from agent.observability import trace_url_for
from agent.telemetry import trace_span
from apps.api.auth.security import AuthenticatedUser
from apps.api.context import AppContext
from apps.api.dependencies import get_context, get_current_user
from apps.api.schemas.api import (
    ApprovalRequest,
    CheckpointHistoryResponse,
    CheckpointReplayResponse,
    CheckpointSummary,
    ParagraphRegenerateRequest,
    ParagraphRegenerateResponse,
    RunResponse,
)

router = APIRouter(prefix="/runs", tags=["runs"])
ACTIVE_RUN_STATUSES = {"queued", "analysing", "drafting", "revising"}


async def _authorized_state(
    context: AppContext, thread_id: str, user: AuthenticatedUser
) -> dict[str, object]:
    snapshot = await context.graph.aget_state({"configurable": {"thread_id": thread_id}})
    values = cast(dict[str, object], jsonable_encoder(snapshot.values))
    if values.get("user_id") != user.user_id or values.get("tenant_id") != user.tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return values


@router.get("/{thread_id}", response_model=RunResponse)
async def get_run(
    thread_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> RunResponse:
    state = await _authorized_state(context, thread_id, user)
    trace_id = str(state["trace_id"]) if state.get("trace_id") else None
    return RunResponse(
        thread_id=thread_id,
        status=str(state.get("status", "unknown")),
        state=state,
        trace_id=trace_id,
        trace_url=trace_url_for(trace_id),
    )


@router.get("/{thread_id}/history", response_model=CheckpointHistoryResponse)
async def get_run_history(
    thread_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CheckpointHistoryResponse:
    await _authorized_state(context, thread_id, user)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    checkpoints: list[CheckpointSummary] = []
    async for snapshot in context.graph.aget_state_history(config):
        encoded_config = cast(dict[str, object], jsonable_encoder(snapshot.config or {}))
        configurable = encoded_config.get("configurable")
        if not isinstance(configurable, dict):
            continue
        checkpoint_id = configurable.get("checkpoint_id")
        if not checkpoint_id:
            continue
        values = cast(dict[str, object], jsonable_encoder(snapshot.values))
        raw_step_count = values.get("step_count", 0)
        step_count = int(raw_step_count) if isinstance(raw_step_count, str | int | float) else 0
        checkpoints.append(
            CheckpointSummary(
                checkpoint_id=str(checkpoint_id),
                created_at=snapshot.created_at,
                status=str(values.get("status", "unknown")),
                next_nodes=list(snapshot.next),
                step_count=step_count,
            )
        )
        if len(checkpoints) >= limit:
            break
    return CheckpointHistoryResponse(thread_id=thread_id, checkpoints=checkpoints)


@router.get(
    "/{thread_id}/replay/{checkpoint_id}",
    response_model=CheckpointReplayResponse,
)
async def replay_checkpoint(
    thread_id: str,
    checkpoint_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> CheckpointReplayResponse:
    await _authorized_state(context, thread_id, user)
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}
    }
    snapshot = await context.graph.aget_state(config)
    values = cast(dict[str, object], jsonable_encoder(snapshot.values))
    if not values:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    if values.get("user_id") != user.user_id or values.get("tenant_id") != user.tenant_id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    encoded_config = cast(dict[str, object], jsonable_encoder(snapshot.config or {}))
    configurable = encoded_config.get("configurable")
    resolved_id = configurable.get("checkpoint_id") if isinstance(configurable, dict) else None
    if str(resolved_id) != checkpoint_id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return CheckpointReplayResponse(
        thread_id=thread_id,
        checkpoint_id=checkpoint_id,
        status=str(values.get("status", "unknown")),
        next_nodes=list(snapshot.next),
        state=values,
    )


@router.get("/{thread_id}/events")
async def stream_run_events(
    thread_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> EventSourceResponse:
    await _authorized_state(context, thread_id, user)

    async def generate() -> AsyncIterator[dict[str, str]]:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        emitted = 0
        previous_status: str | None = None
        while True:
            snapshot = await context.graph.aget_state(config)
            state = jsonable_encoder(snapshot.values)
            events = state.get("events", [])
            if isinstance(events, list):
                for index, event in enumerate(events[emitted:], start=emitted + 1):
                    yield {"event": "node", "id": str(index), "data": json.dumps(event)}
                emitted = len(events)
            status = str(state.get("status", "unknown"))
            if status != previous_status:
                yield {
                    "event": "status",
                    "data": json.dumps({"thread_id": thread_id, "status": status}),
                }
                previous_status = status
            if status not in ACTIVE_RUN_STATUSES:
                return
            await asyncio.sleep(0.25)

    return EventSourceResponse(generate(), ping=15)


@router.post("/{thread_id}/approval", response_model=RunResponse)
async def decide_approval(
    thread_id: str,
    request: ApprovalRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> RunResponse:
    await _authorized_state(context, thread_id, user)
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    current = await context.graph.aget_state(config)
    if current.values.get("status") != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Run is not awaiting approval")
    current_trace_id = str(current.values.get("trace_id") or "")
    with trace_span(
        "gigbid.bid_graph.resume",
        {
            "gigbid.trace_id": current_trace_id,
            "gigbid.thread_id": thread_id,
            "gigbid.graph": "bid",
        },
    ):
        await context.graph.ainvoke(Command(resume=request.model_dump(mode="json")), config)
    snapshot = await context.graph.aget_state(config)
    state = jsonable_encoder(snapshot.values)
    trace_id = str(state["trace_id"]) if state.get("trace_id") else None
    return RunResponse(
        thread_id=thread_id,
        status=str(state.get("status", "unknown")),
        state=state,
        trace_id=trace_id,
        trace_url=trace_url_for(trace_id),
    )


@router.post(
    "/{thread_id}/regenerate-paragraph",
    response_model=ParagraphRegenerateResponse,
)
async def regenerate_run_paragraph(
    thread_id: str,
    request: ParagraphRegenerateRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> ParagraphRegenerateResponse:
    state = await _authorized_state(context, thread_id, user)
    if state.get("status") != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Run is not awaiting approval")
    try:
        replacement, reasons = regenerate_paragraph(
            draft=ProposalDraft.model_validate(state["proposal_draft"]),
            paragraph_index=request.paragraph_index,
            job=JobSpec.model_validate(state["job_spec"]),
            evidence=[
                EvidenceItem.model_validate(item)
                for item in cast(list[object], state["evidence"])
            ],
            price=PriceQuote.model_validate(state["price_quote"]),
        )
    except IndexError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ParagraphRegenerateResponse(
        paragraph_index=request.paragraph_index,
        replacement=replacement,
        reasons=reasons,
    )
