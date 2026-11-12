from __future__ import annotations

import asyncio
from collections import deque
from time import monotonic

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agent.handoffs import DryRunPreview, MarketplaceReceipt


def _retryable_status(error: BaseException) -> bool:
    return isinstance(error, httpx.HTTPStatusError) and (
        error.response.status_code == 429 or error.response.status_code >= 500
    )


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self.timestamps: deque[float] = deque()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            now = monotonic()
            while self.timestamps and now - self.timestamps[0] >= 60:
                self.timestamps.popleft()
            if len(self.timestamps) >= self.limit:
                await asyncio.sleep(60 - (now - self.timestamps[0]))
            self.timestamps.append(monotonic())


class PerTenantRateLimiter:
    """Keep each tenant below the configured upstream request ceiling."""

    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = requests_per_minute
        self.limiters: dict[str, SlidingWindowRateLimiter] = {}
        self.lock = asyncio.Lock()

    async def acquire(self, tenant_id: str) -> None:
        async with self.lock:
            limiter = self.limiters.setdefault(
                tenant_id,
                SlidingWindowRateLimiter(self.requests_per_minute),
            )
        await limiter.acquire()


class GigSimAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        requests_per_minute: int = 20,
        timeout_seconds: float = 15,
    ) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=timeout_seconds,
        )
        self.limiter = PerTenantRateLimiter(requests_per_minute)

    async def aclose(self) -> None:
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=(
            retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
            | retry_if_exception(_retryable_status)
        ),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> object:
        tenant_id = (params or {}).get("tenant_id") or str((json_body or {}).get("tenant_id", ""))
        await self.limiter.acquire(tenant_id or "anonymous")
        response = await self.client.request(
            method,
            path,
            params=params,
            json=json_body,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    async def search_jobs(self, *, tenant_id: str, query: str) -> list[dict[str, object]]:
        result = await self._request("GET", "/jobs", params={"q": query, "tenant_id": tenant_id})
        return _mapping_list(result)

    async def get_job(self, *, tenant_id: str, job_id: str) -> dict[str, object]:
        result = await self._request("GET", f"/jobs/{job_id}", params={"tenant_id": tenant_id})
        return _mapping(result)

    async def get_client_history(self, *, tenant_id: str, client_id: str) -> dict[str, object]:
        result = await self._request(
            "GET", f"/clients/{client_id}", params={"tenant_id": tenant_id}
        )
        return _mapping(result)

    async def get_connects_balance(self, *, tenant_id: str) -> int:
        result = await self._request("GET", "/connects", params={"tenant_id": tenant_id})
        return _required_int(_mapping(result).get("balance"), field="balance")

    async def list_messages(
        self, *, tenant_id: str, conversation_id: str
    ) -> list[dict[str, object]]:
        result = await self._request(
            "GET", f"/conversations/{conversation_id}/messages", params={"tenant_id": tenant_id}
        )
        return _mapping_list(result)

    async def preview_proposal(
        self, *, tenant_id: str, payload: dict[str, object]
    ) -> DryRunPreview:
        result = await self._request(
            "POST",
            "/proposals/draft",
            json_body={**payload, "tenant_id": tenant_id, "dry_run": True},
        )
        return DryRunPreview.model_validate(result)

    async def create_proposal_draft(
        self,
        *,
        tenant_id: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        result = await self._request(
            "POST",
            "/proposals/draft",
            headers={"Idempotency-Key": idempotency_key},
            json_body={**payload, "tenant_id": tenant_id, "dry_run": False},
        )
        return MarketplaceReceipt.model_validate(result)

    async def submit_proposal(
        self,
        *,
        tenant_id: str,
        proposal_id: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        result = await self._request(
            "POST",
            f"/proposals/{proposal_id}/submit",
            headers={"Idempotency-Key": idempotency_key},
            json_body={"tenant_id": tenant_id},
        )
        return MarketplaceReceipt.model_validate(result)

    async def send_message(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        body: str,
        idempotency_key: str,
    ) -> MarketplaceReceipt:
        result = await self._request(
            "POST",
            f"/conversations/{conversation_id}/messages",
            headers={"Idempotency-Key": idempotency_key},
            json_body={"tenant_id": tenant_id, "body": body},
        )
        return MarketplaceReceipt.model_validate(result)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("GigSim response must be a JSON object")
    return {str(key): item for key, item in value.items()}


def _mapping_list(value: object) -> list[dict[str, object]]:
    raw_items = value if isinstance(value, list) else _mapping(value).get("items")
    if not isinstance(raw_items, list):
        raise ValueError("GigSim response must contain an items list")
    if not all(isinstance(item, dict) for item in raw_items):
        raise ValueError("GigSim items contained a non-object value")
    return [{str(key): item for key, item in record.items()} for record in raw_items]


def _required_int(value: object, *, field: str) -> int:
    if not isinstance(value, (str, int, float)):
        raise ValueError(f"GigSim field {field!r} must be numeric")
    return int(value)
