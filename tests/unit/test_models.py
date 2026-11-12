import json

import httpx
import respx

from agent.models import ModelRouter, OpenModelClient


@respx.mock
async def test_ollama_client_returns_structured_usage() -> None:
    route = respx.post("http://models.test/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {"content": '{"cover_letter":"Grounded","screening_answers":{}}'},
                "prompt_eval_count": 21,
                "eval_count": 8,
            },
        )
    )
    client = OpenModelClient(provider="ollama", base_url="http://models.test")

    result = await client.complete_json(model="open-small", system="system", user="user")

    assert route.called
    request = json.loads(route.calls.last.request.content)
    assert request["think"] is False
    assert request["options"]["num_predict"] == 1024
    assert result.data["cover_letter"] == "Grounded"
    assert result.tokens == 29


@respx.mock
async def test_model_router_uses_configured_fallback() -> None:
    route = respx.post("http://models.test/api/chat").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(
                200,
                json={
                    "message": {
                        "content": '{"cover_letter":"Fallback","screening_answers":{}}'
                    },
                    "prompt_eval_count": 10,
                    "eval_count": 4,
                },
            ),
        ]
    )
    router = ModelRouter(
        client=OpenModelClient(provider="ollama", base_url="http://models.test"),
        nodes={"writer": "open-large"},
        fallback_model="open-small",
    )

    result = await router.generate_json(
        node="writer",
        prompt_name="writer.v1.md",
        payload={"job": {"description": "untrusted"}},
    )

    assert route.call_count == 2
    assert result.model == "open-small"
    assert result.fallback_used is True
