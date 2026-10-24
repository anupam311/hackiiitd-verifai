"""FastAPI app factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.ai.client import LLMClient, OpenAIClient
from app.auth.providers import GoogleProvider, OAuthProvider
from app.config import Settings, get_settings
from app.discovery.base import DiscoveryProvider
from app.discovery.retry import RetryPolicy
from app.errors import error_response, new_request_id, register_error_handlers
from app.repositories.base import Store
from app.repositories.sqlite import SqliteStore, sqlite_path
from app.routes import auth, discovery, health, opportunities, runs, saved
from app.runs.manager import RunManager


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
            oauth_providers["google"] = GoogleProvider(settings.google_client_id,
                                                       settings.google_client_secret.get_secret_value())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await app.state.runs.shutdown()

    app = FastAPI(
        lifespan=lifespan,
        title="VERIFAI API",
        version="0.1.0",
        docs_url=None if prod else "/docs",
        redoc_url=None,
        openapi_url=None if prod else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    allowed_origins = set(settings.cors_origin_list) | {settings.public_base_url.rstrip("/")}

    @app.middleware("http")
    async def origin_guard(request: Request, call_next):
        # Defense in depth for cookie sessions: browsers always send Origin on cross-site writes.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in allowed_origins:
                return error_response(request, 403, "FORBIDDEN", "Cross-origin request blocked.")
        return await call_next(request)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = new_request_id()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.state.store = store or SqliteStore(sqlite_path(settings.database_url))
    app.state.provider, app.state.llm = provider, llm
    app.state.settings, app.state.oauth_providers = settings, oauth_providers
    app.state.runs = run_manager or RunManager()
    app.state.retry_policy = retry_policy or RetryPolicy()
    app.state.extract_retry_policy = extract_retry_policy or RetryPolicy(max_attempts=3, timeout_s=60.0)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(opportunities.router)
    app.include_router(discovery.router)
    app.include_router(runs.router)
    app.include_router(saved.router)
    app.include_router(auth.router)
    return app


app = create_app()