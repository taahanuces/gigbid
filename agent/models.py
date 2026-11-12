from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import httpx

from agent.telemetry import trace_span

PROMPTS = Path(__file__).with_name("prompts")


@dataclass(frozen=True, slots=True)
class ModelCallResult:
    data: dict[str, Any]
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    fallback_used: bool = False

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class OpenModelClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 45,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def complete_json(
        self, *, model: str, system: str, user: str
    ) -> ModelCallResult:
        started = perf_counter()
        with trace_span(
            "gen_ai.chat",
            {
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": self.provider,
                "gen_ai.request.model": model,
            },
        ) as span:
            if self.provider == "ollama":
                data, prompt_tokens, completion_tokens = await self._ollama(
                    model=model, system=system, user=user
                )
            elif self.provider == "openai_compatible":
                data, prompt_tokens, completion_tokens = await self._openai_compatible(
                    model=model, system=system, user=user
                )
            else:
                raise ValueError(f"Unsupported model provider: {self.provider}")
            latency_ms = (perf_counter() - started) * 1_000
            span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
            span.set_attribute("gigbid.latency_ms", round(latency_ms, 3))
            return ModelCallResult(
                data=data,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
            )

    async def _ollama(
        self, *, model: str, system: str, user: str
    ) -> tuple[dict[str, Any], int, int]:
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout_seconds
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "format": "json",
                    "think": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "options": {
                        "temperature": 0,
                        "seed": 4016,
                        "num_predict": 1024,
                    },
                },
            )
            response.raise_for_status()
        body = cast(dict[str, Any], response.json())
        message = body.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("Ollama response did not contain message.content")
        return (
            _json_object(message["content"]),
            int(body.get("prompt_eval_count") or 0),
            int(body.get("eval_count") or 0),
        )

    async def _openai_compatible(
        self, *, model: str, system: str, user: str
    ) -> tuple[dict[str, Any], int, int]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            response.raise_for_status()
        body = cast(dict[str, Any], response.json())
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("OpenAI-compatible response did not contain choices")
        first = choices[0]
        if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
            raise ValueError("OpenAI-compatible response did not contain a message")
        content = first["message"].get("content")
        if not isinstance(content, str):
            raise ValueError("OpenAI-compatible response did not contain message content")
        raw_usage = body.get("usage")
        usage: dict[str, Any] = (
            cast(dict[str, Any], raw_usage) if isinstance(raw_usage, dict) else {}
        )
        return (
            _json_object(content),
            int(usage.get("prompt_tokens") or 0),
            int(usage.get("completion_tokens") or 0),
        )


def _json_object(content: str) -> dict[str, Any]:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Model response must be one JSON object")
    return cast(dict[str, Any], value)


class ModelRouter:
    def __init__(
        self,
        *,
        client: OpenModelClient,
        nodes: dict[str, str],
        fallback_model: str | None,
    ) -> None:
        self.client = client
        self.nodes = nodes
        self.fallback_model = fallback_model

    @classmethod
    def from_config(cls, models: dict[str, Any]) -> ModelRouter:
        profile_name = os.getenv("MODEL_PROFILE", str(models.get("profile", "open")))
        profiles = models.get("profiles")
        if not isinstance(profiles, dict) or not isinstance(profiles.get(profile_name), dict):
            raise ValueError(f"Unknown model profile: {profile_name}")
        profile = cast(dict[str, Any], profiles[profile_name])
        nodes = profile.get("nodes")
        if not isinstance(nodes, dict):
            raise ValueError(f"Model profile {profile_name} has no node routing")
        base_url = str(profile.get("base_url") or os.getenv("OPEN_MODEL_BASE_URL", ""))
        if not base_url:
            raise ValueError(f"Model profile {profile_name} has no base_url")
        return cls(
            client=OpenModelClient(
                provider=str(profile.get("provider", "ollama")),
                base_url=base_url,
                api_key=os.getenv("OPEN_MODEL_API_KEY") or None,
            ),
            nodes={str(key): str(value) for key, value in nodes.items()},
            fallback_model=(
                str(profile["fallback_model"]) if profile.get("fallback_model") else None
            ),
        )

    async def generate_json(
        self,
        *,
        node: str,
        prompt_name: str,
        payload: dict[str, object],
    ) -> ModelCallResult:
        model = self.nodes[node]
        system = (PROMPTS / prompt_name).read_text(encoding="utf-8")
        user = "<UNTRUSTED_INPUT>\n" + json.dumps(payload, sort_keys=True) + "\n</UNTRUSTED_INPUT>"
        try:
            return await self.client.complete_json(model=model, system=system, user=user)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            if not self.fallback_model or self.fallback_model == model:
                raise
            result = await self.client.complete_json(
                model=self.fallback_model,
                system=system,
                user=user,
            )
            return ModelCallResult(
                data=result.data,
                model=result.model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                latency_ms=result.latency_ms,
                fallback_used=True,
            )
