from datetime import datetime, timezone
from typing import Any

from app.db import get_db
from app.errors import ConflictError, NotFoundError
from app.models.registry import ModelCreate, ModelRecord, ModelUpdate

CACHE_TTL_SECONDS = 60

_cache: list[ModelRecord] | None = None
_cache_loaded_at: float | None = None

# Prices below are public OpenRouter list prices (USD / 1M tokens) where known.
# Unknown prices are left as null and must not be invented.
SEED_MODELS: list[dict[str, Any]] = [
    {
        "model_id": "openrouter/openai/gpt-4o",
        "label": "GPT-4o",
        "provider": "openai",
        "channel": "primary",
        "fallback_model_id": "openrouter/openai/gpt-4o-mini",
        "enabled": True,
        "order": 10,
        "context_window": 128000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 2.5,
        "output_price_per_1m": 10.0,
    },
    {
        "model_id": "openrouter/openai/gpt-4o-mini",
        "label": "GPT-4o Mini",
        "provider": "openai",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 11,
        "context_window": 128000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 0.15,
        "output_price_per_1m": 0.60,
    },
    {
        "model_id": "openrouter/openai/gpt-4-turbo",
        "label": "GPT-4 Turbo",
        "provider": "openai",
        "channel": "secondary",
        "fallback_model_id": "openrouter/openai/gpt-4o-mini",
        "enabled": True,
        "order": 12,
        "context_window": 128000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 10.0,
        "output_price_per_1m": 30.0,
    },
    {
        "model_id": "openrouter/openai/o1-mini",
        "label": "o1 Mini",
        "provider": "openai",
        "channel": "secondary",
        "fallback_model_id": "openrouter/openai/gpt-4o-mini",
        "enabled": True,
        "order": 13,
        "context_window": 128000,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 3.0,
        "output_price_per_1m": 12.0,
    },
    {
        "model_id": "openrouter/anthropic/claude-3.5-sonnet",
        "label": "Claude 3.5 Sonnet",
        "provider": "anthropic",
        "channel": "primary",
        "fallback_model_id": "openrouter/anthropic/claude-3-haiku",
        "enabled": True,
        "order": 20,
        "context_window": 200000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 3.0,
        "output_price_per_1m": 15.0,
    },
    {
        "model_id": "openrouter/anthropic/claude-3-opus",
        "label": "Claude 3 Opus",
        "provider": "anthropic",
        "channel": "secondary",
        "fallback_model_id": "openrouter/anthropic/claude-3.5-sonnet",
        "enabled": True,
        "order": 21,
        "context_window": 200000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 15.0,
        "output_price_per_1m": 75.0,
    },
    {
        "model_id": "openrouter/anthropic/claude-3-haiku",
        "label": "Claude 3 Haiku",
        "provider": "anthropic",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 22,
        "context_window": 200000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 0.25,
        "output_price_per_1m": 1.25,
    },
    {
        "model_id": "openrouter/google/gemini-2.0-flash-001",
        "label": "Gemini 2.0 Flash",
        "provider": "google",
        "channel": "primary",
        "fallback_model_id": "openrouter/google/gemini-flash-1.5",
        "enabled": True,
        "order": 30,
        "context_window": 1000000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 0.10,
        "output_price_per_1m": 0.40,
    },
    {
        "model_id": "openrouter/google/gemini-pro-1.5",
        "label": "Gemini 1.5 Pro",
        "provider": "google",
        "channel": "secondary",
        "fallback_model_id": "openrouter/google/gemini-flash-1.5",
        "enabled": True,
        "order": 31,
        "context_window": 2000000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 1.25,
        "output_price_per_1m": 5.0,
    },
    {
        "model_id": "openrouter/google/gemini-flash-1.5",
        "label": "Gemini 1.5 Flash",
        "provider": "google",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 32,
        "context_window": 1000000,
        "supports_streaming": True,
        "supports_vision": True,
        "input_price_per_1m": 0.075,
        "output_price_per_1m": 0.30,
    },
    {
        "model_id": "openrouter/x-ai/grok-2-1212",
        "label": "Grok 2",
        "provider": "xai",
        "channel": "primary",
        "fallback_model_id": "openrouter/x-ai/grok-2-mini",
        "enabled": True,
        "order": 40,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/x-ai/grok-2-mini",
        "label": "Grok 2 Mini",
        "provider": "xai",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 41,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/deepseek/deepseek-chat",
        "label": "DeepSeek Chat",
        "provider": "deepseek",
        "channel": "primary",
        "fallback_model_id": "openrouter/deepseek/deepseek-r1",
        "enabled": True,
        "order": 50,
        "context_window": 64000,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 0.14,
        "output_price_per_1m": 0.28,
    },
    {
        "model_id": "openrouter/deepseek/deepseek-r1",
        "label": "DeepSeek R1",
        "provider": "deepseek",
        "channel": "secondary",
        "fallback_model_id": "openrouter/deepseek/deepseek-chat",
        "enabled": True,
        "order": 51,
        "context_window": 64000,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 0.55,
        "output_price_per_1m": 2.19,
    },
    {
        "model_id": "openrouter/meta-llama/llama-3.3-70b-instruct",
        "label": "Llama 3.3 70B",
        "provider": "meta",
        "channel": "primary",
        "fallback_model_id": "openrouter/meta-llama/llama-3.1-8b-instruct",
        "enabled": True,
        "order": 60,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 0.12,
        "output_price_per_1m": 0.30,
    },
    {
        "model_id": "openrouter/meta-llama/llama-3.1-8b-instruct",
        "label": "Llama 3.1 8B",
        "provider": "meta",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 61,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 0.02,
        "output_price_per_1m": 0.05,
    },
    {
        "model_id": "openrouter/meta-llama/llama-3.1-405b-instruct",
        "label": "Llama 3.1 405B",
        "provider": "meta",
        "channel": "secondary",
        "fallback_model_id": "openrouter/meta-llama/llama-3.3-70b-instruct",
        "enabled": True,
        "order": 62,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/mistralai/mistral-large",
        "label": "Mistral Large",
        "provider": "mistral",
        "channel": "primary",
        "fallback_model_id": "openrouter/mistralai/mistral-small",
        "enabled": True,
        "order": 70,
        "context_window": 128000,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 2.0,
        "output_price_per_1m": 6.0,
    },
    {
        "model_id": "openrouter/mistralai/mistral-small",
        "label": "Mistral Small",
        "provider": "mistral",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 71,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 0.20,
        "output_price_per_1m": 0.60,
    },
    {
        "model_id": "openrouter/mistralai/mixtral-8x7b-instruct",
        "label": "Mixtral 8x7B",
        "provider": "mistral",
        "channel": "secondary",
        "fallback_model_id": "openrouter/mistralai/mistral-small",
        "enabled": True,
        "order": 72,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": 0.24,
        "output_price_per_1m": 0.24,
    },
    {
        "model_id": "openrouter/moonshotai/kimi-k2",
        "label": "Kimi K2",
        "provider": "moonshot",
        "channel": "primary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 80,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/moonshotai/moonshot-v1-8k",
        "label": "Moonshot v1 8K",
        "provider": "moonshot",
        "channel": "secondary",
        "fallback_model_id": "openrouter/moonshotai/kimi-k2",
        "enabled": True,
        "order": 81,
        "context_window": 8192,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/qwen/qwen-2.5-72b-instruct",
        "label": "Qwen 2.5 72B",
        "provider": "qwen",
        "channel": "primary",
        "fallback_model_id": "openrouter/qwen/qwen-2.5-7b-instruct",
        "enabled": True,
        "order": 90,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/qwen/qwen-2.5-7b-instruct",
        "label": "Qwen 2.5 7B",
        "provider": "qwen",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 91,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/qwen/qwen-2.5-coder-32b-instruct",
        "label": "Qwen 2.5 Coder 32B",
        "provider": "qwen",
        "channel": "secondary",
        "fallback_model_id": "openrouter/qwen/qwen-2.5-72b-instruct",
        "enabled": True,
        "order": 92,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/nvidia/llama-3.1-nemotron-70b-instruct",
        "label": "Nemotron 70B",
        "provider": "nvidia",
        "channel": "primary",
        "fallback_model_id": "openrouter/nvidia/nemotron-mini-4b-instruct",
        "enabled": True,
        "order": 100,
        "context_window": 131072,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/nvidia/nemotron-mini-4b-instruct",
        "label": "Nemotron Mini 4B",
        "provider": "nvidia",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 101,
        "context_window": 4096,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/minimax/minimax-01",
        "label": "MiniMax-01",
        "provider": "minimax",
        "channel": "primary",
        "fallback_model_id": "openrouter/minimax/minimax-m1",
        "enabled": True,
        "order": 110,
        "context_window": 1000000,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
    {
        "model_id": "openrouter/minimax/minimax-m1",
        "label": "MiniMax M1",
        "provider": "minimax",
        "channel": "secondary",
        "fallback_model_id": None,
        "enabled": True,
        "order": 111,
        "context_window": 1000000,
        "supports_streaming": True,
        "supports_vision": False,
        "input_price_per_1m": None,
        "output_price_per_1m": None,
    },
]


def invalidate_cache() -> None:
    global _cache, _cache_loaded_at
    _cache = None
    _cache_loaded_at = None


def _doc_to_record(doc: dict[str, Any]) -> ModelRecord:
    return ModelRecord(
        model_id=doc["model_id"],
        label=doc["label"],
        provider=doc["provider"],
        channel=doc.get("channel", "primary"),
        fallback_model_id=doc.get("fallback_model_id"),
        enabled=bool(doc.get("enabled", True)),
        order=int(doc.get("order", 0)),
        context_window=int(doc.get("context_window", 128000)),
        supports_streaming=bool(doc.get("supports_streaming", True)),
        supports_vision=bool(doc.get("supports_vision", False)),
        input_price_per_1m=doc.get("input_price_per_1m"),
        output_price_per_1m=doc.get("output_price_per_1m"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


async def seed_models() -> None:
    db = get_db()
    now = datetime.now(timezone.utc)
    for item in SEED_MODELS:
        existing = await db.models.find_one({"model_id": item["model_id"]})
        if existing is not None:
            continue
        await db.models.insert_one({**item, "created_at": now, "updated_at": now})
    invalidate_cache()


async def load_models(*, force: bool = False) -> list[ModelRecord]:
    global _cache, _cache_loaded_at
    import time

    now = time.monotonic()
    if (
        not force
        and _cache is not None
        and _cache_loaded_at is not None
        and now - _cache_loaded_at < CACHE_TTL_SECONDS
    ):
        return _cache
    db = get_db()
    docs = await db.models.find({}).sort("order", 1).to_list(length=500)
    _cache = [_doc_to_record(doc) for doc in docs]
    _cache_loaded_at = now
    return _cache


async def list_enabled_models() -> list[ModelRecord]:
    models = await load_models()
    return [model for model in models if model.enabled]


async def list_all_models() -> list[ModelRecord]:
    return await load_models()


async def get_model(model_id: str) -> ModelRecord | None:
    models = await load_models()
    for model in models:
        if model.model_id == model_id:
            return model
    return None


async def create_model(payload: ModelCreate) -> ModelRecord:
    db = get_db()
    existing = await db.models.find_one({"model_id": payload.model_id})
    if existing is not None:
        raise ConflictError("model_id already exists")
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    await db.models.insert_one(doc)
    invalidate_cache()
    return _doc_to_record(doc)


async def update_model(model_id: str, payload: ModelUpdate) -> ModelRecord:
    db = get_db()
    updates = {key: value for key, value in payload.model_dump(exclude_unset=True).items()}
    if not updates:
        record = await get_model(model_id)
        if record is None:
            raise NotFoundError("Model not found")
        return record
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db.models.update_one({"model_id": model_id}, {"$set": updates})
    if result.matched_count == 0:
        raise NotFoundError("Model not found")
    invalidate_cache()
    doc = await db.models.find_one({"model_id": model_id})
    if doc is None:
        raise NotFoundError("Model not found")
    return _doc_to_record(doc)


async def delete_model(model_id: str) -> None:
    db = get_db()
    result = await db.models.delete_one({"model_id": model_id})
    if result.deleted_count == 0:
        raise NotFoundError("Model not found")
    invalidate_cache()
