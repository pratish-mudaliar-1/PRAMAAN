"""app/core/errors.py — RFC 9457 Problem+JSON global error handling."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class ProblemDetail(BaseModel):
    """RFC 9457 problem detail object."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str = ""
    # extensions
    request_id: str = ""
    errors: list[dict[str, Any]] | None = None


def _problem_response(
    status_code: int,
    title: str,
    detail: str,
    request: Request | None = None,
    errors: list[dict[str, Any]] | None = None,
    type_uri: str = "about:blank",
) -> JSONResponse:
    request_id = ""
    instance = ""
    if request:
        request_id = str(request.state.request_id) if hasattr(request.state, "request_id") else ""
        instance = str(request.url)

    body = ProblemDetail(
        type=type_uri,
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        request_id=request_id,
        errors=errors,
    ).model_dump(exclude_none=True)

    return JSONResponse(
        content=body,
        status_code=status_code,
        headers={"Content-Type": "application/problem+json"},
    )


# ── Custom application exceptions ────────────────────────────────────────────

class PramaanError(Exception):
    """Base class for all domain / application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    title: str = "Internal Server Error"
    type_uri: str = "about:blank"

    def __init__(self, detail: str, *, request_id: str = "") -> None:
        super().__init__(detail)
        self.detail = detail
        self.request_id = request_id


class NotFoundError(PramaanError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Resource Not Found"
    type_uri = "/problems/not-found"

    def __init__(self, resource_or_detail: str, identifier: str = "", *, request_id: str = "") -> None:
        if identifier:
            detail = f"{resource_or_detail} '{identifier}' not found"
        else:
            detail = resource_or_detail
        super().__init__(detail, request_id=request_id)


class ConflictError(PramaanError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"
    type_uri = "/problems/conflict"


class AuthenticationError(PramaanError):
    status_code = status.HTTP_401_UNAUTHORIZED
    title = "Authentication Failed"
    type_uri = "/problems/authentication-failed"


class AuthorizationError(PramaanError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Access Denied"
    type_uri = "/problems/access-denied"


class ValidationError(PramaanError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    title = "Validation Error"
    type_uri = "/problems/validation-error"


class RateLimitError(PramaanError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    title = "Too Many Requests"
    type_uri = "/problems/rate-limit-exceeded"


class IntegrityError(PramaanError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    title = "Data Integrity Error"
    type_uri = "/problems/integrity-error"


# ── Exception handlers ────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PramaanError)
    async def _pramaan_error(request: Request, exc: PramaanError) -> JSONResponse:
        logger.warning("application_error", error=exc.detail, type=type(exc).__name__)
        return _problem_response(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            request=request,
            type_uri=exc.type_uri,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem_response(
            status_code=exc.status_code,
            title="HTTP Error",
            detail=exc.detail or "",
            request=request,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return _problem_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Request Validation Error",
            detail="One or more fields failed validation.",
            request=request,
            errors=errors,
            type_uri="/problems/validation-error",
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        error_id = str(uuid.uuid4())
        logger.exception("unhandled_exception", error_id=error_id, exc_info=exc)
        return _problem_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail=f"An unexpected error occurred. Error ID: {error_id}",
            request=request,
        )
