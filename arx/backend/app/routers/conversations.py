from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import get_current_user
from app.errors import NotFoundError
from app.models.chat import ConversationDetail, ConversationRename, ConversationSummary, MessagePublic
from app.models.user import UserInDB

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise NotFoundError("Conversation not found") from exc


def _summary(doc: dict) -> ConversationSummary:
    return ConversationSummary(
        id=str(doc["_id"]),
        title=doc.get("title") or "New chat",
        model_id=doc.get("model_id") or "",
        message_count=int(doc.get("message_count") or 0),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        archived=bool(doc.get("archived", False)),
    )


def _message(doc: dict) -> MessagePublic:
    return MessagePublic(
        id=str(doc["_id"]),
        conversation_id=str(doc["conversation_id"]),
        role=doc["role"],
        content=doc.get("content") or "",
        model_id=doc.get("model_id"),
        tokens_in=doc.get("tokens_in"),
        tokens_out=doc.get("tokens_out"),
        latency_ms=doc.get("latency_ms"),
        first_token_ms=doc.get("first_token_ms"),
        sources=doc.get("sources") or [],
        created_at=doc["created_at"],
    )


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(user: UserInDB = Depends(get_current_user)) -> list[ConversationSummary]:
    db = get_db()
    docs = (
        await db.conversations.find({"user_id": user.id, "archived": {"$ne": True}})
        .sort("updated_at", -1)
        .to_list(length=200)
    )
    return [_summary(doc) for doc in docs]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    user: UserInDB = Depends(get_current_user),
) -> ConversationDetail:
    db = get_db()
    doc = await db.conversations.find_one({"_id": _oid(conversation_id), "user_id": user.id})
    if doc is None:
        raise NotFoundError("Conversation not found")
    messages = (
        await db.messages.find({"conversation_id": conversation_id, "user_id": user.id})
        .sort("created_at", 1)
        .to_list(length=2000)
    )
    summary = _summary(doc)
    return ConversationDetail(**summary.model_dump(), messages=[_message(item) for item in messages])


@router.patch("/{conversation_id}", response_model=ConversationSummary)
async def rename_conversation(
    conversation_id: str,
    payload: ConversationRename,
    user: UserInDB = Depends(get_current_user),
) -> ConversationSummary:
    db = get_db()
    now = datetime.now(timezone.utc)
    result = await db.conversations.update_one(
        {"_id": _oid(conversation_id), "user_id": user.id},
        {"$set": {"title": payload.title, "updated_at": now}},
    )
    if result.matched_count == 0:
        raise NotFoundError("Conversation not found")
    doc = await db.conversations.find_one({"_id": _oid(conversation_id)})
    assert doc is not None
    return _summary(doc)


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: UserInDB = Depends(get_current_user),
) -> dict[str, bool]:
    db = get_db()
    result = await db.conversations.delete_one({"_id": _oid(conversation_id), "user_id": user.id})
    if result.deleted_count == 0:
        raise NotFoundError("Conversation not found")
    await db.messages.delete_many({"conversation_id": conversation_id, "user_id": user.id})
    return {"ok": True}
