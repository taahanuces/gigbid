from __future__ import annotations

import hashlib
import hmac
import os
from base64 import b64decode, b64encode
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    role: str = "reviewer"


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    actual_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), actual_salt, 310_000)
    return f"{b64encode(actual_salt).decode()}:{b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    salt_text, digest_text = encoded.split(":", 1)
    candidate = hash_password(password, salt=b64decode(salt_text)).split(":", 1)[1]
    return hmac.compare_digest(candidate, digest_text)


def create_access_token(user: AuthenticatedUser, *, secret: str, minutes: int = 60) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.user_id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, *, secret: str) -> AuthenticatedUser:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid or expired access token") from exc
    return AuthenticatedUser(
        user_id=str(payload["sub"]),
        tenant_id=str(payload["tenant_id"]),
        email=str(payload["email"]),
        role=str(payload.get("role", "reviewer")),
    )
