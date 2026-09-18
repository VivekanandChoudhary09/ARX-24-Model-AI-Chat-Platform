from collections.abc import Callable

from fastapi import Depends, Request

from app.errors import AuthRejected
from app.models.user import UserInDB
from app.services.security import (
    PUBLIC_PATHS,
    check_internal_key,
    check_origin,
    extract_bearer,
    require_admin,
    verify_jwt_and_session,
)


async def require_internal_key(request: Request) -> None:
    if request.url.path in PUBLIC_PATHS:
        return
    check_internal_key(request.headers.get("x-internal-key") or request.headers.get("X-Internal-Key"))


async def origin_guard_dependency(request: Request) -> None:
    if request.url.path in PUBLIC_PATHS:
        return
    provided = request.headers.get("x-internal-key") or request.headers.get("X-Internal-Key")
    from app.config import get_settings

    has_valid = bool(provided and provided == get_settings().INTERNAL_API_KEY)
    check_origin(
        request.headers.get("origin"),
        request.headers.get("referer") or request.headers.get("referrer"),
        has_valid,
    )


async def get_current_user(
    request: Request,
    _: None = Depends(origin_guard_dependency),
    __: None = Depends(require_internal_key),
) -> UserInDB:
    token = extract_bearer(request)
    if not token:
        raise AuthRejected("Authorization bearer token is required")
    user, jti = await verify_jwt_and_session(token)
    request.state.user = user
    request.state.jti = jti
    return user


async def get_current_admin(user: UserInDB = Depends(get_current_user)) -> UserInDB:
    require_admin(user)
    return user


def protected(*deps: Callable[..., object]) -> list[Depends]:
    return [Depends(dep) for dep in deps]
