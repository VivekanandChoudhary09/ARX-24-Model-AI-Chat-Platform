from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.errors import InferenceError
from app.models.registry import RouteDecision


DisconnectCheck = Callable[[], Awaitable[bool]]


@dataclass
class StreamResult:
    text: str
    tokens_in: int
    tokens_out: int
    first_token_ms: int | None
    cancelled: bool
    model_id: str
    used_fallback: bool


class StreamCancelled(Exception):
    """Raised when the client disconnects mid-stream."""


async def _stream_model(
    *,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float | None,
    is_disconnected: DisconnectCheck | None,
) -> AsyncIterator[tuple[str, dict[str, Any] | None]]:
    """Yield (token, usage_or_none) from LiteLLM. usage is set on the final chunk when present."""
    import litellm

    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "stream": True,
        "api_key": settings.OPENROUTER_API_KEY or None,
        "api_base": settings.OPENROUTER_BASE_URL,
        "stream_options": {"include_usage": True},
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = await litellm.acompletion(**kwargs)
    async for chunk in response:
        if is_disconnected is not None and await is_disconnected():
            close = getattr(response, "aclose", None) or getattr(response, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            raise StreamCancelled()
        delta = ""
        usage = None
        try:
            choices = getattr(chunk, "choices", None) or []
            if choices:
                message_delta = choices[0].delta
                delta = getattr(message_delta, "content", None) or ""
            usage_obj = getattr(chunk, "usage", None)
            if usage_obj is not None:
                usage = {
                    "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
                    "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
                }
        except Exception:
            delta = ""
        if delta or usage:
            yield delta, usage


async def stream_with_failover(
    *,
    route: RouteDecision,
    messages: list[dict[str, str]],
    temperature: float | None,
    is_disconnected: DisconnectCheck | None = None,
) -> AsyncIterator[tuple[str, str, dict[str, Any] | None]]:
    """
    Stage 5 — stream from the selected model; on error retry once on fallback.

    Yields (token, active_model_id, usage). Fallback is transparent to the caller:
    tokens from the fallback are yielded the same way, without an error frame.
    """
    primary_error: Exception | None = None
    try:
        async for token, usage in _stream_model(
            model_id=route.model_id,
            messages=messages,
            temperature=temperature,
            is_disconnected=is_disconnected,
        ):
            yield token, route.model_id, usage
        return
    except StreamCancelled:
        raise
    except Exception as exc:
        primary_error = exc
        if not route.fallback_model_id:
            raise InferenceError(f"Inference failed: {exc}") from exc

    try:
        async for token, usage in _stream_model(
            model_id=route.fallback_model_id,
            messages=messages,
            temperature=temperature,
            is_disconnected=is_disconnected,
        ):
            yield token, route.fallback_model_id, usage
    except StreamCancelled:
        raise
    except Exception as exc:
        raise InferenceError(
            f"Inference failed on primary and fallback: {primary_error}; {exc}"
        ) from exc
