from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol

from app.config import get_settings
from app.errors import QuotaExceeded


class QuotaBackend(Protocol):
    async def get(self, key: str) -> int: ...
    async def incr_by(self, key: str, amount: int) -> int: ...


class MemoryQuotaBackend:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._store: dict[str, int] = {}

    async def get(self, key: str) -> int:
        async with self._lock:
            return self._store.get(key, 0)

    async def incr_by(self, key: str, amount: int) -> int:
        async with self._lock:
            current = self._store.get(key, 0) + amount
            self._store[key] = current
            return current


class RedisQuotaBackend:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> int:
        value = await self._client.get(key)
        return int(value) if value is not None else 0

    async def incr_by(self, key: str, amount: int) -> int:
        return int(await self._client.incrby(key, amount))


_backend: QuotaBackend | None = None


def init_quota_backend() -> QuotaBackend:
    global _backend
    settings = get_settings()
    if settings.REDIS_URL:
        _backend = RedisQuotaBackend(settings.REDIS_URL)
    else:
        _backend = MemoryQuotaBackend()
    return _backend


def get_quota_backend() -> QuotaBackend:
    if _backend is None:
        return init_quota_backend()
    return _backend


def set_quota_backend(backend: QuotaBackend) -> None:
    global _backend
    _backend = backend


def user_quota_key(user_id: str, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m")
    return f"quota:user:{user_id}:{stamp}"


def ip_quota_key(ip: str, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d-%H")
    return f"quota:ip:{ip}:{stamp}"


def _month_reset(now: datetime) -> datetime:
    year = now.year + (1 if now.month == 12 else 0)
    month = 1 if now.month == 12 else now.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _hour_reset(now: datetime) -> datetime:
    truncated = now.replace(minute=0, second=0, microsecond=0)
    from datetime import timedelta

    return truncated + timedelta(hours=1)


async def check_quota(*, user_id: str, monthly_limit: int, ip: str, ip_limit: int | None = None) -> None:
    """Stage 2 — enforce monthly user tokens and hourly IP requests before inference."""
    settings = get_settings()
    backend = get_quota_backend()
    now = datetime.now(timezone.utc)
    ip_cap = ip_limit if ip_limit is not None else settings.DEFAULT_IP_HOURLY_REQUESTS

    used_user = await backend.get(user_quota_key(user_id, now))
    if used_user >= monthly_limit:
        raise QuotaExceeded(
            "Monthly token quota exceeded",
            limit=monthly_limit,
            used=used_user,
            resets_at=_month_reset(now),
        )

    used_ip = await backend.get(ip_quota_key(ip, now))
    if used_ip >= ip_cap:
        raise QuotaExceeded(
            "Hourly IP request quota exceeded",
            limit=ip_cap,
            used=used_ip,
            resets_at=_hour_reset(now),
        )


async def increment_user_tokens(user_id: str, tokens: int) -> int:
    if tokens <= 0:
        return await get_quota_backend().get(user_quota_key(user_id))
    return await get_quota_backend().incr_by(user_quota_key(user_id), tokens)


async def increment_ip_requests(ip: str) -> int:
    return await get_quota_backend().incr_by(ip_quota_key(ip), 1)
