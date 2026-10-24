"""Standard error shape from docs/api.md: {"error": {code, message, request_id}}.

Hardening notes (B16):
- 422 Unprocessable Entity from Pydantic is re-mapped to 400 VALIDATION_ERROR so callers
  never need to handle two "invalid input" status codes.
- 405 Method Not Allowed gets a standard body (FastAPI's default is plain text).
- Unexpected exceptions are logged with run ID / request ID but no request content.
- Rate-limited responses (429) include a Retry-After header when the delay is known.
"""
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("verifai.api")

_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",  # re-mapped from Pydantic's default 422
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:16]}"


def error_response(request: Request, status: int, code: str, message: str,
                   extra_headers: dict[str, str] | None = None) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or new_request_id()
    headers = {"X-Request-ID": request_id}
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        # 422 from FastAPI's own path/query validation: normalize to 400.
        status = 400 if exc.status_code == 422 else exc.status_code
        code = _CODES.get(status, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        extra: dict[str, str] = {}
        if status == 429:
            # Some callers set exc.headers with Retry-After; propagate it.
            if hasattr(exc, "headers") and exc.headers and "Retry-After" in exc.headers:
                extra["Retry-After"] = exc.headers["Retry-After"]
        return error_response(request, status, code, message, extra or None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Field details are omitted on purpose: inputs may contain personal data.
        return error_response(request, 400, "VALIDATION_ERROR", "The request could not be processed.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "unhandled error request_id=%s type=%s",
            request_id, type(exc).__name__,
            # No exc_info=True: avoids logging request content embedded in the traceback.
        )
        return error_response(request, 500, "INTERNAL_ERROR", "An unexpected error occurred.")