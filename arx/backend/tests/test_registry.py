from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def auth_headers(token: str | None = None) -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Origin": "http://localhost:3000",
        "X-Internal-Key": settings.INTERNAL_API_KEY,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def test_registry_insert_without_restart() -> None:
    email = f"admin-{uuid.uuid4().hex[:10]}@example.com"
    model_id = f"openrouter/test/arx-insert-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        if not client.get("/health").json().get("mongo"):
            pytest.skip("MongoDB is not available")
        register = client.post(
            "/api/auth/register",
            json={"email": email, "password": "password12"},
            headers=auth_headers(),
        )
        assert register.status_code == 200, register.text
        token = register.json()["access_token"]
        user = register.json()["user"]
        if user["role"] != "admin":
            from anyio.from_thread import run as run_async
            from bson import ObjectId

            from app.db import get_db

            async def _promote() -> None:
                await get_db().users.update_one(
                    {"_id": ObjectId(user["id"])},
                    {"$set": {"role": "admin"}},
                )

            run_async(_promote)

        created = client.post(
            "/api/models",
            json={
                "model_id": model_id,
                "label": "ARX Insert Probe",
                "provider": "openai",
                "enabled": True,
                "order": 999,
                "context_window": 8192,
                "supports_streaming": True,
                "supports_vision": False,
            },
            headers=auth_headers(token),
        )
        assert created.status_code == 200, created.text
        listed = client.get("/api/models", headers=auth_headers(token))
        assert listed.status_code == 200
        ids = [item["model_id"] for item in listed.json()["models"]]
        assert model_id in ids

        async def fake_stream(*_args: Any, **_kwargs: Any):
            yield "ok", model_id, {"prompt_tokens": 1, "completion_tokens": 1}

        with patch("app.routers.chat.stream_with_failover", fake_stream):
            chat = client.post(
                "/api/chat",
                json={
                    "conversation_id": None,
                    "message": "hello from registry probe",
                    "model_id": model_id,
                    "use_rag": False,
                },
                headers=auth_headers(token),
            )
        assert chat.status_code == 200, chat.text
        assert "data:" in chat.text
        client.delete(f"/api/models/{model_id}", headers=auth_headers(token))
