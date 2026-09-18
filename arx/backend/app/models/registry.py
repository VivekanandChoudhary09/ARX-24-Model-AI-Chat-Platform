from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Channel = Literal["primary", "secondary"]


class ModelRecord(BaseModel):
    model_id: str
    label: str
    provider: str
    channel: Channel = "primary"
    fallback_model_id: str | None = None
    enabled: bool = True
    order: int = 0
    context_window: int = 128000
    supports_streaming: bool = True
    supports_vision: bool = False
    input_price_per_1m: float | None = None
    output_price_per_1m: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ModelCreate(BaseModel):
    model_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    channel: Channel = "primary"
    fallback_model_id: str | None = None
    enabled: bool = True
    order: int = 0
    context_window: int = 128000
    supports_streaming: bool = True
    supports_vision: bool = False
    input_price_per_1m: float | None = None
    output_price_per_1m: float | None = None


class ModelUpdate(BaseModel):
    label: str | None = None
    provider: str | None = None
    channel: Channel | None = None
    fallback_model_id: str | None = None
    enabled: bool | None = None
    order: int | None = None
    context_window: int | None = None
    supports_streaming: bool | None = None
    supports_vision: bool | None = None
    input_price_per_1m: float | None = None
    output_price_per_1m: float | None = None


class ModelListResponse(BaseModel):
    models: list[ModelRecord]


class RouteDecision(BaseModel):
    model_id: str
    label: str
    provider: str
    channel: Channel
    fallback_model_id: str | None = None
    context_window: int
    input_price_per_1m: float | None = None
    output_price_per_1m: float | None = None
