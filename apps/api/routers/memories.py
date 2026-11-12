from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status

from agent.memory.promotion_rules import OutcomeObservation
from agent.memory.store import LongTermMemory
from apps.api.auth.security import AuthenticatedUser
from apps.api.context import AppContext
from apps.api.dependencies import get_context, get_current_user
from apps.api.schemas.api import MemoryItem, OutcomeRequest, OutcomeResponse

router = APIRouter(prefix="/memories", tags=["memories"])


def _memory(context: AppContext, user: AuthenticatedUser) -> LongTermMemory:
    if context.store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Long-term memory store is unavailable",
        )
    return LongTermMemory(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        style_minimum_consistent_edits=context.config.memory.style_minimum_consistent_edits,
        outcome_minimum_observations=context.config.memory.outcome_minimum_observations,
        outcome_minimum_reply_rate=context.config.memory.outcome_minimum_reply_rate,
    )


def context_path() -> str:
    from apps.api.context import ROOT

    return str(ROOT / "agent/config.yaml")


@router.get("", response_model=list[MemoryItem])
async def list_memories(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> list[MemoryItem]:
    promoted = await _memory(context, user).list_promoted()
    return [MemoryItem.model_validate(item.model_dump()) for item in promoted]


@router.post("/outcomes", response_model=OutcomeResponse)
async def record_outcome(
    request: OutcomeRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> OutcomeResponse:
    promoted = await _memory(context, user).record_outcome(
        OutcomeObservation(**request.model_dump())
    )
    return OutcomeResponse(
        promoted=(
            MemoryItem.model_validate(promoted.model_dump())
            if promoted is not None
            else None
        )
    )


@router.delete("/{kind}/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    kind: Literal["style", "outcome"],
    key: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> Response:
    await _memory(context, user).delete_promoted(kind, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
