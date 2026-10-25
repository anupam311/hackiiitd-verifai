"""Application settings, read from VERIFAI_* environment variables.

All secrets use SecretStr so they are never accidentally logged or included in tracebacks.
Settings are validated at startup; a missing required value is caught before any request is served.
"""
import json
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERIFAI_", env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"  # comma-separated (a JSON list is also accepted)
    database_url: str = "sqlite:///./verifai.db"
    # Connection pool size for PostgreSQL (ignored for SQLite).
    # Neon serverless: keep this low (2-5); each idle connection holds a Neon compute unit.
    database_pool_size: int = Field(default=5, ge=1, le=20)

    # Provider credentials: server-side only. No default model is assumed; choose one explicitly.
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str | None = Field(default=None, validation_alias="OPENAI_MODEL")

    # TinyFish live discovery (radar.py integration). Without a key the discovery provider is not configured.
    # Search is free; each agent run costs credits, so max_pages bounds the cost of one discovery request.
    tinyfish_api_key: SecretStr | None = Field(default=None, validation_alias="TINYFISH_API_KEY")
    tinyfish_max_pages: int = Field(default=5, ge=1, le=20)  # VERIFAI_TINYFISH_MAX_PAGES
    tinyfish_max_concurrency: int = Field(default=3, ge=1, le=10)  # agents running at once
    tinyfish_agent_timeout_s: float = Field(default=240.0, gt=0, le=1800)  # per page
    tinyfish_stealth: bool = False  # browser_profile=STEALTH for sites that block bots
    tinyfish_seed_pages: str = ""  # comma-separated careers pages always included (radar.py PAGES)

    # Auth. public_base_url is where THIS API is reachable by the browser: it builds the OAuth
    # redirect URI (never derived from request headers). frontend_url is where users land after
    # sign-in.
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    session_ttl_days: int = 7

    google_client_id: str | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret: SecretStr | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_SECRET")
    github_client_id: str | None = Field(default=None, validation_alias="GITHUB_OAUTH_CLIENT_ID")
    github_client_secret: SecretStr | None = Field(default=None, validation_alias="GITHUB_OAUTH_CLIENT_SECRET")

    # Production security settings
    # Trusted hosts: comma-separated list (e.g. "api.example.com,localhost").
    # Empty string disables the check (development default).
    trusted_hosts: str = ""

    # Maximum allowed request body size in bytes (default: 1 MB).
    # Protects against oversized payloads that could cause memory pressure.
    max_request_body_bytes: int = Field(default=1_048_576, ge=1, le=104_857_600)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw.startswith("["):
            try:
                return [str(o).strip() for o in json.loads(raw)]
            except ValueError:
                pass
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        """Non-empty list of trusted hosts, or [] to disable the check."""
        raw = self.trusted_hosts.strip()
        if not raw:
            return []
        return [h.strip() for h in raw.split(",") if h.strip()]

    @property
    def tinyfish_seed_page_list(self) -> list[str]:
        return [u.strip() for u in self.tinyfish_seed_pages.split(",") if u.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()