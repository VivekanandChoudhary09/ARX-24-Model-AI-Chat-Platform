from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Request
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.db import get_db
from app.errors import AuthRejected, ForbiddenError, InternalKeyRejected, OriginRejected
from app.models.user import UserInDB

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

PUBLIC_PATHS = {"/health", "/api/health", "/docs", "/openapi.json", "/redoc"}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def user_from_doc(doc: dict[str, Any]) -> UserInDB:
    return UserInDB(
        id=str(doc["_id"]),
        email=doc["email"],
        role=doc["role"],
        plan=doc.get("plan", "free"),
        monthly_token_quota=int(doc.get("monthly_token_quota", get_settings().DEFAULT_MONTHLY_TOKEN_QUOTA)),
        created_at=doc["created_at"],
        last_login_at=doc.get("last_login_at"),
        is_active=bool(doc.get("is_active", True)),
    )


def _origin_host(value: str) -> str:
    return value.split("?", 1)[0].rstrip("/")


def origin_allowed(origin: str | None, referer: str | None, allowed: list[str]) -> bool:
    allowed_norm = {_origin_host(item) for item in allowed}
    if origin:
        return _origin_host(origin) in allowed_norm
    if referer:
        # Referer is a full URL; compare scheme+host[+port]
        trimmed = referer.split("?", 1)[0]
        for allowed_origin in allowed_norm:
            if trimmed == allowed_origin or trimmed.startswith(allowed_origin + "/"):
                return True
        return False
    return False


def check_origin(origin: str | None, referer: str | None, has_valid_internal_key: bool) -> None:
    """
    Independent origin guard (not CORS).

    Browser requests must present an allowlisted Origin or Referer.
    Next.js server-to-server calls should send Origin: http://localhost:3000.
    If both headers are absent, only a valid X-Internal-Key is accepted
    (pytest / Next.js BFF without Origin). Off-list Origin/Referer always fails.
    """
    settings = get_settings()
    allowed = settings.allowed_origins_list
    if origin or referer:
        if not origin_allowed(origin, referer, allowed):
            raise OriginRejected("Origin or Referer is not allowlisted")
        return
    if has_valid_internal_key:
        return
    raise OriginRejected("Origin or Referer header is required")


def check_internal_key(provided: str | None) -> None:
    settings = get_settings()
    if not provided or provided != settings.INTERNAL_API_KEY:
        raise InternalKeyRejected("X-Internal-Key is missing or invalid")


def create_access_token(*, user_id: str, jti: str, expires_at: datetime) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "jti": jti,
        "iat": datetime.now(timezone.utc),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def issue_session(
    *,
    user_id: str,
    user_agent: str | None,
    ip: str | None,
) -> tuple[str, str]:
    settings = get_settings()
    jti = uuid4().hex
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    db = get_db()
    await db.sessions.insert_one(
        {
            "user_id": user_id,
            "jti": jti,
            "issued_at": now,
            "expires_at": expires_at,
            "revoked": False,
            "user_agent": user_agent,
            "ip": ip,
        }
    )
    token = create_access_token(user_id=user_id, jti=jti, expires_at=expires_at)
    return token, jti


async def revoke_session(jti: str) -> None:
    db = get_db()
    await db.sessions.update_one({"jti": jti}, {"$set": {"revoked": True}})


async def verify_jwt_and_session(token: str) -> tuple[UserInDB, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthRejected("Invalid or expired token") from exc

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise AuthRejected("Token is missing required claims")

    db = get_db()
    session = await db.sessions.find_one({"jti": jti})
    if session is None:
        raise AuthRejected("Session was not found")
    if session.get("revoked"):
        raise AuthRejected("Session has been revoked")

    expires_at = session.get("expires_at")
    if expires_at is None:
        raise AuthRejected("Session has no expiry")
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise AuthRejected("Session has expired")

    from bson import ObjectId

    try:
        oid = ObjectId(user_id)
    except Exception as exc:
        raise AuthRejected("Token subject is invalid") from exc

    user_doc = await db.users.find_one({"_id": oid})
    if user_doc is None or not user_doc.get("is_active", True):
        raise AuthRejected("User is inactive or missing")
    return user_from_doc(user_doc), jti


def require_admin(user: UserInDB) -> None:
    if user.role != "admin":
        raise ForbiddenError("Admin role is required")


def extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
