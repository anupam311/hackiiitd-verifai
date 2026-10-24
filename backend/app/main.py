"""FastAPI app factory.

Production checklist items handled here:
- Security response headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
  Permissions-Policy, Cache-Control for auth endpoints)
- Optional TrustedHostMiddleware when VERIFAI_TRUSTED_HOSTS is set
- Optional request body size guard (VERIFAI_MAX_REQUEST_BODY_BYTES)
- Origin guard (defense-in-depth for cookie sessions)
- Request ID attached to every response
- /docs and /openapi.json disabled in production
- Startup log summary of active integrations (never logs secrets)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.client import LLMClient, OpenAIClient
from app.auth.github import GitHubProvider
from app.auth.providers import GoogleProvider, OAuthProvider
from app.config import Settings, get_settings
from app.discovery.base import DiscoveryProvider
from app.discovery.retry import RetryPolicy
from app.errors import error_response, new_request_id, register_error_handlers
from app.repositories.base import Store
from app.repositories.sqlite import SqliteStore, sqlite_path
from app.routes import auth, discovery, health, opportunities, profile, runs, saved
from app.runs.manager import RunManager

logger = logging.getLogger("verifai.app")

# Security headers added to every response.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}
# Auth paths get a no-store cache header so tokens never land in browser history.
_AUTH_PATHS = {"/auth"}


def create_app(
    settings: Settings | None = None,
    *,
    store: Store | None = None,
    provider: DiscoveryProvider | None = None,  # real TinyFish adapter is not implemented yet
    llm: LLMClient | None = None,
    run_manager: RunManager | None = None,
    retry_policy: RetryPolicy | None = None,
    extract_retry_policy: RetryPolicy | None = None,
    oauth_providers: dict[str, OAuthProvider] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)
    prod = settings.is_production

    if llm is None and settings.openai_api_key and settings.openai_model:
        llm = OpenAIClient(settings.openai_api_key.get_secret_value(), settings.openai_model)

    if oauth_providers is None:
        oauth_providers = {}
        if settings.google_client_id and settings.google_client_secret:
            oauth_providers["google"] = GoogleProvider(
                settings.google_client_id,
                settings.google_client_secret.get_secret_value())
        if settings.github_client_id and settings.github_client_secret:
            oauth_providers["github"] = GitHubProvider(
                settings.github_client_id,
                settings.github_client_secret.get_secret_value())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Log startup summary — never includes secret values.
        logger.info(
            "verifai startup env=%s providers=%s llm=%s oauth=%s db=%s",
            settings.env,
            "none" if provider is None else getattr(provider, "name", "custom"),
            "none" if llm is None else getattr(llm, "name", "custom"),
            list(oauth_providers.keys()) if oauth_providers else [],
            settings.database_url.split("://")[0],  # scheme only, not path
        )
        yield
        await app.state.runs.shutdown()
        logger.info("verifai shutdown complete")

    app = FastAPI(
        lifespan=lifespan,
        title="VERIFAI API",
        version="0.1.0",
        docs_url=None if prod else "/docs",
        redoc_url=None,
        openapi_url=None if prod else "/openapi.json",
    )

    # ------------------------------------------------------------------ #
    # Middleware — order matters: outermost wrapper runs last on response. #
    # ------------------------------------------------------------------ #

    # CORS must come before the origin-guard middleware.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    # Optional TrustedHostMiddleware (production: set VERIFAI_TRUSTED_HOSTS).
    trusted = settings.trusted_host_list
    if trusted:
        from starlette.middleware.trustedhost import TrustedHostMiddleware
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted)

    allowed_origins = set(settings.cors_origin_list) | {settings.public_base_url.rstrip("/")}

    # Security headers + auth cache-control
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        # Prevent caching of auth responses (tokens must not land in history/cache)
        if request.url.path.startswith("/auth"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
        return response

    # Origin guard — defense in depth for cookie sessions.
    @app.middleware("http")
    async def origin_guard(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in allowed_origins:
                return error_response(request, 403, "FORBIDDEN", "Cross-origin request blocked.")
        return await call_next(request)

    # Request body size guard — rejects oversized payloads early.
    max_body = settings.max_request_body_bytes

    @app.middleware("http")
    async def body_size_guard(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_body:
                    return JSONResponse(
                        status_code=413,
                        content={"error": {"code": "PAYLOAD_TOO_LARGE",
                                           "message": "Request body exceeds the allowed limit.",
                                           "request_id": new_request_id()}},
                    )
            except ValueError:
                pass
        return await call_next(request)

    # Request ID — injected before every other middleware sees the response.
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = new_request_id()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    # ------------------------------------------------------------------ #
    # App state                                                            #
    # ------------------------------------------------------------------ #
    app.state.store = store or SqliteStore(sqlite_path(settings.database_url))
    app.state.provider, app.state.llm = provider, llm
    app.state.settings, app.state.oauth_providers = settings, oauth_providers
    app.state.runs = run_manager or RunManager()
    app.state.retry_policy = retry_policy or RetryPolicy()
    app.state.extract_retry_policy = extract_retry_policy or RetryPolicy(max_attempts=3, timeout_s=60.0)

    # ------------------------------------------------------------------ #
    # Routes                                                               #
    # ------------------------------------------------------------------ #
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(opportunities.router)
    app.include_router(discovery.router)
    app.include_router(runs.router)
    app.include_router(saved.router)
    app.include_router(auth.router)
    app.include_router(profile.router)
    return app


app = create_app()