from __future__ import annotations

from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from agent.graphs.conversation_graph import ConversationState
from agent.observability import current_trace_id
from agent.telemetry import trace_span
from apps.api.auth.security import AuthenticatedUser
from apps.api.context import AppContext
from apps.api.dependencies import get_context, get_current_user
from apps.api.schemas.api import (
    ApprovalRequest,
    ConversationRunResponse,
    ConversationStartRequest,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _authorized_state(
    context: AppContext, thread_id: str, user: AuthenticatedUser
) -> dict[str, object]:
    snapshot = await context.conversation_graph.aget_state(
        {"configurable": {"thread_id": thread_id}}
    )
    values = cast(dict[str, object], jsonable_encoder(snapshot.values))
    if values.get("user_id") != user.user_id or values.get("tenant_id") != user.tenant_id:
        raise HTTPException(status_code=404, detail="Conversation run not found")
    return values


@router.post("/{conversation_id}/draft", response_model=ConversationRunResponse)
async def start_conversation_run(
    conversation_id: str,
    request: ConversationStartRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> ConversationRunResponse:
    thread_id = str(uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    initial: ConversationState = {
        "thread_id": thread_id,
        "tenant_id": user.tenant_id,
        "user_id": user.user_id,
        "conversation_id": conversation_id,
        "inbound_message": request.inbound_message,
        "free_slots": request.free_slots,
        "step_count": 0,
        "events": [],
        "errors": [],
    }
    with trace_span(
        "gigbid.conversation_graph",
        {
            "gigbid.trace_id": current_trace_id(),
            "gigbid.thread_id": thread_id,
            "gigbid.graph": "conversation",
        },
    ):
        await context.conversation_graph.ainvoke(initial, config)
    snapshot = await context.conversation_graph.aget_state(config)
    state = cast(dict[str, object], jsonable_encoder(snapshot.values))
    return ConversationRunResponse(
        thread_id=thread_id,
        conversation_id=conversation_id,
        status=str(state.get("status", "unknown")),
        state=state,
    )


@router.get("/runs/{thread_id}", response_model=ConversationRunResponse)
async def get_conversation_run(
    thread_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> ConversationRunResponse:
    state = await _authorized_state(context, thread_id, user)
    return ConversationRunResponse(
        thread_id=thread_id,
        conversation_id=str(state["conversation_id"]),
        status=str(state.get("status", "unknown")),
        state=state,
    )


@router.post("/runs/{thread_id}/approval", response_model=ConversationRunResponse)
async def approve_conversation_run(
    thread_id: str,
    request: ApprovalRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> ConversationRunResponse:
    state = await _authorized_state(context, thread_id, user)
    if state.get("status") != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Conversation is not awaiting approval")
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    with trace_span(
        "gigbid.conversation_graph.resume",
        {
            "gigbid.trace_id": current_trace_id(),
            "gigbid.thread_id": thread_id,
            "gigbid.graph": "conversation",
        },
    ):
        await context.conversation_graph.ainvoke(
            Command(resume=request.model_dump(mode="json")), config
        )
    snapshot = await context.conversation_graph.aget_state(config)
    updated = cast(dict[str, object], jsonable_encoder(snapshot.values))
    return ConversationRunResponse(
        thread_id=thread_id,
        conversation_id=str(updated["conversation_id"]),
        status=str(updated.get("status", "unknown")),
        state=updated,
    )
