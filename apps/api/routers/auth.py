from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.auth.security import create_access_token, verify_password
from apps.api.context import AppContext
from apps.api.dependencies import get_context
from apps.api.schemas.api import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    context: Annotated[AppContext, Depends(get_context)],
) -> TokenResponse:
    record = context.users.get(request.email.lower())
    if record is None or not verify_password(request.password, record.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(record.user, secret=context.secret))
