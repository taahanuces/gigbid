from __future__ import annotations

import os
from hmac import compare_digest

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings


class StaticBearerTokenVerifier(TokenVerifier):
    """Verify the service token used between GigBid and its owned MCP servers."""

    def __init__(self, token: str, resource_url: str) -> None:
        self._token = token
        self._resource_url = resource_url

    async def verify_token(self, token: str) -> AccessToken | None:
        if not compare_digest(token, self._token):
            return None
        return AccessToken(
            token=token,
            client_id="gigbid-api",
            subject="gigbid-service",
            scopes=["mcp"],
            resource=self._resource_url,
        )


def bearer_auth(
    resource_url: str,
) -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Return MCP auth components; tests may omit the token for in-memory calls."""

    token = os.getenv("MCP_BEARER_TOKEN", "").strip()
    if not token:
        return None, None
    verifier = StaticBearerTokenVerifier(token, resource_url)
    settings = AuthSettings(
        issuer_url="https://gigbid.local",
        resource_server_url=resource_url,
        required_scopes=["mcp"],
        validate_token_resource=True,
    )
    return verifier, settings
