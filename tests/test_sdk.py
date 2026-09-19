from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from evalplatform import sdk
from evalplatform.sdk import current_trace, observe


@pytest.fixture
def captured() -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/traces"
        seen.append(json.loads(request.content))
        return httpx.Response(202, json={"id": "x", "score_status": "pending"})

    sdk.configure("http://eval.local", transport=httpx.MockTransport(handler))
    return seen


def test_observe_sync(captured: list[dict[str, Any]]) -> None:
    @observe(name="chat", model="gpt-4o-mini", provider="openai", metrics=["toxicity"])
    def answer(question: str) -> str:
        current_trace().update(input_tokens=12, context=["doc"])
        return f"echo: {question}"

    assert answer("hello") == "echo: hello"
    sdk.flush()
    [t] = captured
    assert t["name"] == "chat" and t["input"] == "hello" and t["output"] == "echo: hello"
    assert t["model"] == "gpt-4o-mini" and t["metrics"] == ["toxicity"]
    assert t["input_tokens"] == 12 and t["context"] == ["doc"]
    assert t["latency_ms"] >= 0


async def test_observe_async_and_errors(captured: list[dict[str, Any]]) -> None:
    @observe()
    async def generate(prompt: str) -> str:
        return prompt.upper()

    @observe(name="boom")
    def failing(prompt: str) -> str:
        raise ValueError("nope")

    assert await generate("hi") == "HI"
    with pytest.raises(ValueError):
        failing("x")
    sdk.flush()
    assert captured[0]["output"] == "HI" and captured[0]["name"].endswith("generate")
    assert captured[1]["status"] == "error" and "ValueError" in captured[1]["metadata"]["error"]


def test_sdk_never_raises_on_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    client = sdk.configure("http://eval.local", transport=httpx.MockTransport(handler))

    @observe()
    def f(x: str) -> str:
        return x

    assert f("ok") == "ok"
    sdk.flush()
    assert client.failed == 1


def test_current_trace_outside_observe() -> None:
    with pytest.raises(RuntimeError):
        current_trace()
