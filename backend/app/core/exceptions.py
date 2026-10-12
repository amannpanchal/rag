"""Centralized application exceptions and FastAPI error handlers."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Not authorized") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409)


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many login attempts. Try again later.") -> None:
        super().__init__(message, status_code=429)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
            msg = err.get("msg", "Invalid input")
            messages.append(f"{loc}: {msg}" if loc else msg)
        return JSONResponse(
            status_code=422,
            content={"detail": messages[0] if len(messages) == 1 else messages},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
        settings = get_settings()
        logger.exception("Unhandled error: %s", exc)
        detail = "An unexpected error occurred."
        if settings.ENVIRONMENT == "development" and settings.DEBUG:
            detail = str(exc)
        return JSONResponse(status_code=500, content={"detail": detail})
