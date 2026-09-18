from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.errors import QuotaExceeded
from app.services.quota import (
    MemoryQuotaBackend,
    check_quota,
    increment_user_tokens,
    set_quota_backend,
    user_quota_key,
)


@pytest.mark.asyncio
async def test_quota_429_structure() -> None:
    backend = MemoryQuotaBackend()
    set_quota_backend(backend)
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    await increment_user_tokens(user_id, 10)
    with pytest.raises(QuotaExceeded) as exc_info:
        await check_quota(user_id=user_id, monthly_limit=10, ip="127.0.0.1", ip_limit=1000)
    body = exc_info.value.to_body()
    assert exc_info.value.status_code == 429
    assert body["code"] == "quota_exceeded"
    assert body["limit"] == 10
    assert body["used"] == 10
    assert "resets_at" in body
    datetime.fromisoformat(body["resets_at"])


@pytest.mark.asyncio
async def test_quota_is_global_across_models() -> None:
    backend = MemoryQuotaBackend()
    set_quota_backend(backend)
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    await increment_user_tokens(user_id, 5)
    key = user_quota_key(user_id, datetime.now(timezone.utc))
    used = await backend.get(key)
    assert used == 5
    with pytest.raises(QuotaExceeded):
        await check_quota(user_id=user_id, monthly_limit=5, ip="10.0.0.2", ip_limit=1000)
