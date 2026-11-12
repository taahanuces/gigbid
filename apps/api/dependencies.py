from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.auth.security import AuthenticatedUser, decode_access_token
from apps.api.context import AppContext

bearer = HTTPBearer(auto_error=False)


def get_context(request: Request) -> AppContext:
    return cast(AppContext, request.app.state.context)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    context: Annotated[AppContext, Depends(get_context)],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    try:
        return decode_access_token(credentials.credentials, secret=context.secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
