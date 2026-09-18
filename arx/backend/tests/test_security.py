from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def _headers(token: str | None = None, include_key: bool = True) -> dict[str, str]:
    settings = get_settings()
    headers = {"Origin": "http://localhost:3000"}
    if include_key:
        headers["X-Internal-Key"] = settings.INTERNAL_API_KEY
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def test_health_mongo() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "mongo" in body
    if not body["mongo"]:
        pytest.skip("MongoDB is not available")


def test_missing_internal_key_rejected() -> None:
    with TestClient(app) as client:
        if not client.get("/health").json().get("mongo"):
            pytest.skip("MongoDB is not available")
        response = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "password12"},
            headers={"Origin": "http://localhost:3000"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "internal_key_rejected"


def test_revoked_session_rejected() -> None:
    email = f"revoke-{uuid.uuid4().hex[:10]}@example.com"
    with TestClient(app) as client:
        if not client.get("/health").json().get("mongo"):
            pytest.skip("MongoDB is not available")
        register = client.post(
            "/api/auth/register",
            json={"email": email, "password": "password12"},
            headers=_headers(),
        )
        assert register.status_code == 200, register.text
        token = register.json()["access_token"]
        me = client.get("/api/auth/me", headers=_headers(token))
        assert me.status_code == 200
        logout = client.post("/api/auth/logout", headers=_headers(token))
        assert logout.status_code == 200
        rejected = client.get("/api/auth/me", headers=_headers(token))
    assert rejected.status_code == 401
    assert rejected.json()["code"] == "auth_rejected"
