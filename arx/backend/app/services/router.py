from datetime import datetime, timezone
from typing import Any

from app.errors import ModelDisabledError, ModelUnknownError
from app.models.registry import RouteDecision
from app.services import registry as registry_service


async def resolve_route(model_id: str) -> RouteDecision:
    """Stage 4 — resolve model_id against the registry cache and pick fallback."""
    record = await registry_service.get_model(model_id)
    if record is None:
        raise ModelUnknownError(f"Unknown model_id: {model_id}")
    if not record.enabled:
        raise ModelDisabledError(f"Model is disabled: {model_id}")
    return RouteDecision(
        model_id=record.model_id,
        label=record.label,
        provider=record.provider,
        channel=record.channel,
        fallback_model_id=record.fallback_model_id,
        context_window=record.context_window,
        input_price_per_1m=record.input_price_per_1m,
        output_price_per_1m=record.output_price_per_1m,
    )


def estimate_cost_usd(
    *,
    tokens_in: int,
    tokens_out: int,
    input_price_per_1m: float | None,
    output_price_per_1m: float | None,
) -> float:
    if input_price_per_1m is None and output_price_per_1m is None:
        return 0.0
    inp = (tokens_in / 1_000_000) * (input_price_per_1m or 0.0)
    out = (tokens_out / 1_000_000) * (output_price_per_1m or 0.0)
    return round(inp + out, 8)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
