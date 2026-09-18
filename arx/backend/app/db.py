from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> AsyncIOMotorDatabase:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client[settings.MONGODB_DB]
    await ensure_indexes(_db)
    return _db


async def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB is not connected")
    return _db


async def ping_mongo() -> bool:
    if _db is None:
        return False
    try:
        await _db.command("ping")
        return True
    except Exception:
        return False


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create every collection index idempotently at startup."""
    await db.users.create_index("email", unique=True)
    await db.users.create_index("is_active")

    await db.sessions.create_index("jti", unique=True)
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)

    await db.models.create_index("model_id", unique=True)
    await db.models.create_index([("enabled", 1), ("order", 1)])

    await db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
    await db.conversations.create_index("archived")

    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.messages.create_index("user_id")

    await db.usage.create_index(
        [("user_id", 1), ("model_id", 1), ("date", 1)],
        unique=True,
    )
    await db.usage.create_index("date")

    await db.documents.create_index([("user_id", 1), ("created_at", -1)])
    await db.documents.create_index("status")
    await db.documents.create_index("excluded")
