from datetime import datetime
from typing import Any


class ArxError(Exception):
    """Typed application error mapped to a structured HTTP response."""

    status_code: int = 400
    code: str = "bad_request"

    def __init__(self, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra or {}

    def to_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        body.update(self.extra)
        return body


class OriginRejected(ArxError):
    status_code = 403
    code = "origin_rejected"


class InternalKeyRejected(ArxError):
    status_code = 401
    code = "internal_key_rejected"


class AuthRejected(ArxError):
    status_code = 401
    code = "auth_rejected"


class ForbiddenError(ArxError):
    status_code = 403
    code = "forbidden"


class NotFoundError(ArxError):
    status_code = 404
    code = "not_found"


class ConflictError(ArxError):
    status_code = 409
    code = "conflict"


class QuotaExceeded(ArxError):
    status_code = 429
    code = "quota_exceeded"

    def __init__(
        self,
        message: str,
        *,
        limit: int,
        used: int,
        resets_at: datetime,
    ) -> None:
        super().__init__(
            message,
            extra={
                "limit": limit,
                "used": used,
                "resets_at": resets_at.isoformat(),
            },
        )


class ModelUnknownError(ArxError):
    status_code = 400
    code = "model_unknown"


class ModelDisabledError(ArxError):
    status_code = 400
    code = "model_disabled"


class InferenceError(ArxError):
    status_code = 502
    code = "inference_error"
