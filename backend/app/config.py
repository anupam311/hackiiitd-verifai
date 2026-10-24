"""Application settings, read from VERIFAI_* environment variables."""
import json
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERIFAI_", env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"  # comma-separated (a JSON list is also accepted)
    database_url: str = "sqlite:///./verifai.db"
    # Provider credentials: server-side only. No default model is assumed; choose one explicitly.
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str | None = Field(default=None, validation_alias="OPENAI_MODEL")
    # Auth. public_base_url is where THIS API is reachable by the browser: it builds the OAuth redirect
    # URI (never derived from request headers). frontend_url is where users land after sign-in.
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    session_ttl_days: int = 7
    google_client_id: str | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret: SecretStr | None = Field(default=None, validation_alias="GOOGLE_OAUTH_CLIENT_SECRET")

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
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()