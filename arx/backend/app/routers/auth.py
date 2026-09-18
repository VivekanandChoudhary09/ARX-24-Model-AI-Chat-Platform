from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user, origin_guard_dependency, require_internal_key
from app.errors import AuthRejected, ConflictError
from app.models.user import AuthResponse, LoginRequest, RegisterRequest, UserInDB, UserPublic
from app.services.security import (
    extract_bearer,
    hash_password,
    issue_session,
    revoke_session,
    user_from_doc,
    verify_jwt_and_session,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_public(user: UserInDB) -> UserPublic:
    return UserPublic(**user.model_dump())


@router.post("/register", response_model=AuthResponse)
async def register(
    payload: RegisterRequest,
    request: Request,
    _: None = Depends(origin_guard_dependency),
    __: None = Depends(require_internal_key),
) -> AuthResponse:
    db = get_db()
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing is not None:
        raise ConflictError("An account with that email already exists")
    user_count = await db.users.count_documents({})
    now = datetime.now(timezone.utc)
    settings = get_settings()
    doc = {
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": "admin" if user_count == 0 else "user",
        "plan": "local",
        "monthly_token_quota": settings.DEFAULT_MONTHLY_TOKEN_QUOTA,
        "created_at": now,
        "last_login_at": now,
        "is_active": True,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    user = user_from_doc(doc)
    token, _jti = await issue_session(
        user_id=str(result.inserted_id),
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    return AuthResponse(user=_to_public(user), access_token=token)


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    _: None = Depends(origin_guard_dependency),
    __: None = Depends(require_internal_key),
) -> AuthResponse:
    db = get_db()
    doc = await db.users.find_one({"email": payload.email.lower()})
    if doc is None or not verify_password(payload.password, doc.get("password_hash", "")):
        raise AuthRejected("Invalid email or password")
    if not doc.get("is_active", True):
        raise AuthRejected("Account is disabled")
    await db.users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc)}},
    )
    user = user_from_doc(doc)
    token, _jti = await issue_session(
        user_id=str(doc["_id"]),
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    return AuthResponse(user=_to_public(user), access_token=token)


@router.post("/logout")
async def logout(
    request: Request,
    user: UserInDB = Depends(get_current_user),
) -> dict[str, bool]:
    del user
    jti = getattr(request.state, "jti", None)
    if jti:
        await revoke_session(jti)
    else:
        token = extract_bearer(request)
        if token:
            _, jti = await verify_jwt_and_session(token)
            await revoke_session(jti)
    return {"ok": True}


@router.get("/me", response_model=UserPublic)
async def me(user: UserInDB = Depends(get_current_user)) -> UserPublic:
    return _to_public(user)
