from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.errors import InferenceError
from app.models.registry import RouteDecision
from app.services.llm import stream_with_failover


def _route(fallback: str | None = "openrouter/openai/gpt-4o-mini") -> RouteDecision:
    return RouteDecision(
        model_id="openrouter/openai/gpt-4o",
        label="GPT-4o",
        provider="openai",
        channel="primary",
        fallback_model_id=fallback,
        context_window=128000,
        input_price_per_1m=2.5,
        output_price_per_1m=10.0,
    )


@pytest.mark.asyncio
async def test_fallback_routing_hides_primary_failure() -> None:
    async def primary_fail(*_args: Any, **kwargs: Any):
        model_id = kwargs["model_id"]
        if model_id.endswith("gpt-4o") and "mini" not in model_id:
            raise RuntimeError("primary down")

        async def gen():
            yield "fallback-ok", {"prompt_tokens": 1, "completion_tokens": 2}

        return gen()

    with patch("app.services.llm._stream_model", new=AsyncMock(side_effect=primary_fail)):
        # _stream_model is an async generator, not a coroutine returning a generator.
        pass

    async def fake_stream(*, model_id: str, **_kwargs: Any):
        if model_id == "openrouter/openai/gpt-4o":
            raise RuntimeError("primary down")
        yield "fallback-ok", {"prompt_tokens": 1, "completion_tokens": 2}

    with patch("app.services.llm._stream_model", fake_stream):
        tokens: list[str] = []
        models: list[str] = []
        async for token, model_id, _usage in stream_with_failover(
            route=_route(),
            messages=[{"role": "user", "content": "hi"}],
            temperature=None,
        ):
            if token:
                tokens.append(token)
                models.append(model_id)
    assert tokens == ["fallback-ok"]
    assert models == ["openrouter/openai/gpt-4o-mini"]


@pytest.mark.asyncio
async def test_fallback_missing_raises_inference_error() -> None:
    async def fake_stream(*, model_id: str, **_kwargs: Any):
        raise RuntimeError("primary down")
        yield  # pragma: no cover

    with patch("app.services.llm._stream_model", fake_stream):
        with pytest.raises(InferenceError):
            async for _ in stream_with_failover(
                route=_route(fallback=None),
                messages=[{"role": "user", "content": "hi"}],
                temperature=None,
            ):
                pass
