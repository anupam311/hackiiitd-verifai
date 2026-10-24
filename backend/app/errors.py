"""Standard error shape from docs/api.md: {"error": {code, message, request_id}}."""
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("verifai.api")

_CODES = {
    400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN",
    404: "NOT_FOUND", 409: "CONFLICT", 429: "RATE_LIMITED", 503: "SERVICE_UNAVAILABLE",
}


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:16]}"


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or new_request_id()
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers={"X-Request-ID": request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = _CODES.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        return error_response(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Field details are omitted on purpose: inputs may contain personal data.
        return error_response(request, 400, "VALIDATION_ERROR", "The request could not be processed.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error("unhandled error request_id=%s type=%s", request_id, type(exc).__name__)
        return error_response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")