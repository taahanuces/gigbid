from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True, slots=True)
class OAuthToken:
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EncryptedTokenRecord:
    tenant_id: str
    provider: str
    access_token_ciphertext: bytes
    refresh_token_ciphertext: bytes | None
    expires_at: datetime | None
    updated_at: datetime


class EncryptedTokenStore:
    """Encrypt OAuth credentials before handing records to the persistence layer."""

    def __init__(
        self,
        encryption_key: str | bytes,
        records: MutableMapping[tuple[str, str], EncryptedTokenRecord] | None = None,
    ) -> None:
        key = encryption_key.encode() if isinstance(encryption_key, str) else encryption_key
        self._fernet = Fernet(key)
        self._records = records if records is not None else {}

    def put(self, tenant_id: str, provider: str, token: OAuthToken) -> None:
        key = (tenant_id, provider)
        self._records[key] = EncryptedTokenRecord(
            tenant_id=tenant_id,
            provider=provider,
            access_token_ciphertext=self._fernet.encrypt(token.access_token.encode()),
            refresh_token_ciphertext=(
                self._fernet.encrypt(token.refresh_token.encode())
                if token.refresh_token is not None
                else None
            ),
            expires_at=token.expires_at,
            updated_at=datetime.now(UTC),
        )

    def get(self, tenant_id: str, provider: str) -> OAuthToken | None:
        record = self._records.get((tenant_id, provider))
        if record is None:
            return None
        try:
            access_token = self._fernet.decrypt(record.access_token_ciphertext).decode()
            refresh_token = (
                self._fernet.decrypt(record.refresh_token_ciphertext).decode()
                if record.refresh_token_ciphertext is not None
                else None
            )
        except InvalidToken as exc:
            raise ValueError("Stored OAuth token could not be decrypted") from exc
        return OAuthToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=record.expires_at,
        )

    def delete(self, tenant_id: str, provider: str) -> bool:
        return self._records.pop((tenant_id, provider), None) is not None

    def list_connections(self, tenant_id: str) -> list[str]:
        return sorted(provider for owner, provider in self._records if owner == tenant_id)
