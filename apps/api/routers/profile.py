from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth.security import AuthenticatedUser
from apps.api.context import AppContext
from apps.api.dependencies import get_context, get_current_user
from apps.api.profile_store import load_profile, save_profile
from apps.api.schemas.api import ProfileResponse, ProfileSettings

router = APIRouter(prefix="/profile", tags=["profile"])


def _evidence_count(context: AppContext, persona: str) -> int:
    index = context.evidence_indexes.get(persona, context.evidence_index)
    return len(index.all())


def _response(context: AppContext, settings: ProfileSettings) -> ProfileResponse:
    return ProfileResponse(
        settings=settings,
        marketplace_mode=context.marketplace_mode,
        evidence_count=_evidence_count(context, settings.persona),
        data_origin="synthetic persona portfolio; public jobs",
    )


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> ProfileResponse:
    settings = await load_profile(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
    )
    return _response(context, settings)


@router.put("", response_model=ProfileResponse)
async def update_profile(
    settings: ProfileSettings,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    context: Annotated[AppContext, Depends(get_context)],
) -> ProfileResponse:
    if context.store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile store is unavailable",
        )
    saved = await save_profile(
        context.store,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        settings=settings,
    )
    return _response(context, saved)
