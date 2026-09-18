from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.db import get_db
from app.deps import get_current_user
from app.errors import ArxError, InferenceError
from app.models.chat import ChatRequest, DoneFrame, ErrorFrame, MetaFrame, SourceChunk, TokenFrame
from app.models.user import UserInDB
from app.services import quota as quota_service
from app.services import retrieval as retrieval_service
from app.services.llm import StreamCancelled, stream_with_failover
from app.services.router import estimate_cost_usd, resolve_route
from app.services.security import client_ip

router = APIRouter(prefix="/api", tags=["chat"])


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _title_from_message(message: str) -> str:
    compact = " ".join(message.strip().split())
    return compact[:72] if compact else "New chat"


def _source_chunks(raw: list[dict[str, Any]]) -> list[SourceChunk]:
    sources: list[SourceChunk] = []
    for item in raw:
        sources.append(
            SourceChunk(
                document_id=str(item.get("document_id") or ""),
                filename=str(item.get("filename") or ""),
                chunk_index=int(item.get("chunk_index") or 0),
                heading=item.get("heading") or None,
                text=str(item.get("text") or ""),
                tags=list(item.get("tags") or []),
            )
        )
    return sources


def _build_messages(
    history: list[dict[str, Any]],
    user_message: str,
    rag_chunks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if rag_chunks:
        context = "\n\n".join(
            f"[{chunk.get('filename')} #{chunk.get('chunk_index')} {chunk.get('heading') or ''}]\n{chunk.get('text')}"
            for chunk in rag_chunks
        )
        messages.append(
            {
                "role": "system",
                "content": (
                    "You are ARX, a multi-model assistant. Ground answers in the following retrieved "
                    "context when it is relevant. If the context is insufficient, say so.\n\n"
                    f"{context}"
                ),
            }
        )
    for item in history:
        role = item.get("role")
        content = item.get("content") or ""
        if role in {"user", "assistant", "system"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    ip = client_ip(request)
    await quota_service.check_quota(user_id=user.id, monthly_limit=user.monthly_token_quota, ip=ip)
    await quota_service.increment_ip_requests(ip)

    rag_result = (
        await retrieval_service.retrieve(payload.message, user_id=user.id)
        if payload.use_rag
        else retrieval_service.RetrievalResult(layer="none", chunks=[])
    )
    route = await resolve_route(payload.model_id)

    db = get_db()
    now = datetime.now(timezone.utc)
    conversation_id = payload.conversation_id
    if conversation_id:
        existing = await db.conversations.find_one({"_id": ObjectId(conversation_id), "user_id": user.id})
        if existing is None:
            conversation_id = None
    if not conversation_id:
        inserted = await db.conversations.insert_one(
            {
                "user_id": user.id,
                "title": _title_from_message(payload.message),
                "model_id": route.model_id,
                "message_count": 0,
                "created_at": now,
                "updated_at": now,
                "archived": False,
            }
        )
        conversation_id = str(inserted.inserted_id)
    else:
        await db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {"model_id": route.model_id, "updated_at": now}},
        )

    history = (
        await db.messages.find({"conversation_id": conversation_id, "user_id": user.id})
        .sort("created_at", 1)
        .to_list(length=100)
    )
    await db.messages.insert_one(
        {
            "conversation_id": conversation_id,
            "user_id": user.id,
            "role": "user",
            "content": payload.message,
            "model_id": route.model_id,
            "tokens_in": None,
            "tokens_out": None,
            "latency_ms": None,
            "first_token_ms": None,
            "sources": [],
            "created_at": now,
        }
    )
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$inc": {"message_count": 1}, "$set": {"updated_at": now}},
    )

    llm_messages = _build_messages(history, payload.message, rag_result.chunks)
    sources = _source_chunks(rag_result.chunks)

    async def is_disconnected() -> bool:
        return await request.is_disconnected()

    async def event_stream() -> AsyncIterator[str]:
        started = time.perf_counter()
        first_token_ms: int | None = None
        collected: list[str] = []
        tokens_in = 0
        tokens_out = 0
        active_model = route.model_id
        billed = False
        cancelled = False

        meta = MetaFrame(conversation_id=conversation_id, model_id=route.model_id, sources=sources)
        yield _sse(meta.model_dump())

        try:
            async for token, active_model, usage in stream_with_failover(
                route=route,
                messages=llm_messages,
                temperature=payload.temperature,
                is_disconnected=is_disconnected,
            ):
                if token:
                    if first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - started) * 1000)
                    collected.append(token)
                    yield _sse(TokenFrame(content=token).model_dump())
                if usage:
                    tokens_in = usage.get("prompt_tokens") or tokens_in
                    tokens_out = usage.get("completion_tokens") or tokens_out
        except StreamCancelled:
            cancelled = True
        except ArxError as exc:
            yield _sse(ErrorFrame(code=exc.code, message=exc.message).model_dump())
            return
        except Exception as exc:
            err = InferenceError(str(exc))
            yield _sse(ErrorFrame(code=err.code, message=err.message).model_dump())
            return

        assistant_text = "".join(collected)
        if tokens_out <= 0:
            tokens_out = len(assistant_text.split())
        if tokens_in <= 0:
            tokens_in = sum(len((item.get("content") or "").split()) for item in llm_messages)

        delivered_tokens = tokens_in + tokens_out
        if assistant_text and not cancelled:
            cost = estimate_cost_usd(
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                input_price_per_1m=route.input_price_per_1m,
                output_price_per_1m=route.output_price_per_1m,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            finished = datetime.now(timezone.utc)
            await db.messages.insert_one(
                {
                    "conversation_id": conversation_id,
                    "user_id": user.id,
                    "role": "assistant",
                    "content": assistant_text,
                    "model_id": active_model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "latency_ms": latency_ms,
                    "first_token_ms": first_token_ms,
                    "sources": [item.model_dump() for item in sources],
                    "created_at": finished,
                }
            )
            await db.conversations.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$inc": {"message_count": 1}, "$set": {"updated_at": finished, "model_id": active_model}},
            )
            day = finished.strftime("%Y-%m-%d")
            await db.usage.update_one(
                {"user_id": user.id, "model_id": active_model, "date": day},
                {
                    "$inc": {
                        "requests": 1,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cost_usd": cost,
                    }
                },
                upsert=True,
            )
            await quota_service.increment_user_tokens(user.id, delivered_tokens)
            billed = True
            yield _sse(
                DoneFrame(
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    first_token_ms=first_token_ms,
                    cost_usd=cost,
                ).model_dump()
            )
        elif cancelled:
            # Undelivered / aborted streams are not billed.
            if assistant_text:
                await db.messages.insert_one(
                    {
                        "conversation_id": conversation_id,
                        "user_id": user.id,
                        "role": "assistant",
                        "content": assistant_text,
                        "model_id": active_model,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "latency_ms": int((time.perf_counter() - started) * 1000),
                        "first_token_ms": first_token_ms,
                        "sources": [item.model_dump() for item in sources],
                        "created_at": datetime.now(timezone.utc),
                    }
                )
            yield _sse(
                DoneFrame(
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    first_token_ms=first_token_ms,
                    cost_usd=0.0,
                ).model_dump()
            )
        del billed

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
