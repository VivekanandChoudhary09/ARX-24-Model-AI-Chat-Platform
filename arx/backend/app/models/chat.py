from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1)
    model_id: str
    use_rag: bool = True
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class SourceChunk(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    heading: str | None = None
    text: str
    tags: list[str] = Field(default_factory=list)


class MetaFrame(BaseModel):
    type: Literal["meta"] = "meta"
    conversation_id: str
    model_id: str
    sources: list[SourceChunk] = Field(default_factory=list)


class TokenFrame(BaseModel):
    type: Literal["token"] = "token"
    content: str


class DoneFrame(BaseModel):
    type: Literal["done"] = "done"
    tokens_in: int
    tokens_out: int
    latency_ms: int
    first_token_ms: int | None
    cost_usd: float


class ErrorFrame(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    model_id: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    archived: bool


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessagePublic(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    model_id: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    first_token_ms: int | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessagePublic] = Field(default_factory=list)
