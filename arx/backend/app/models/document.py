from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


DocumentStatus = Literal["pending", "processing", "ready", "failed"]


class DocumentRecord(BaseModel):
    id: str
    user_id: str
    filename: str
    mime_type: str
    size_bytes: int
    chunk_count: int = 0
    status: DocumentStatus
    excluded: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    error: str | None = None


class DocumentUpdate(BaseModel):
    excluded: bool | None = None
    tags: list[str] | None = None


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=1)


class RagChunk(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    heading: str | None = None
    text: str
    tags: list[str] = Field(default_factory=list)
    excluded: bool = False
    score: float | None = None
    entity: str | None = None


class RagSearchResponse(BaseModel):
    layer: Literal["intent", "anchor", "vector", "none"]
    chunks: list[RagChunk]
