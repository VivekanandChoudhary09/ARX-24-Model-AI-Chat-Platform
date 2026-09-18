from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.db import close_mongo, connect_to_mongo
from app.errors import ArxError
from app.routers import auth, chat, conversations, health, models, rag
from app.services.quota import init_quota_backend
from app.services.registry import seed_models
from app.services.security import PUBLIC_PATHS, check_origin


class OriginGuardMiddleware(BaseHTTPMiddleware):
    """Independent origin check, separate from CORS."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path in PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)
        provided = request.headers.get("x-internal-key") or request.headers.get("X-Internal-Key")
        settings = get_settings()
        has_valid = bool(provided and provided == settings.INTERNAL_API_KEY)
        try:
            check_origin(
                request.headers.get("origin"),
                request.headers.get("referer"),
                has_valid,
            )
        except ArxError as exc:
            return JSONResponse(status_code=exc.status_code, content=exc.to_body())
        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await connect_to_mongo()
    init_quota_backend()
    await seed_models()
    yield
    await close_mongo()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="ARX", version="1.0.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(OriginGuardMiddleware)

    @application.exception_handler(ArxError)
    async def arx_error_handler(_request: Request, exc: ArxError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_body())

    @application.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, isolated_exc: Exception) -> JSONResponse:
        if isinstance(isolated_exc, (StarletteHTTPException, RequestValidationError, ArxError)):
            raise isolated_exc
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": "An unexpected error occurred"},
        )

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(models.router)
    application.include_router(chat.router)
    application.include_router(conversations.router)
    application.include_router(rag.router)
    return application


app = create_app()
