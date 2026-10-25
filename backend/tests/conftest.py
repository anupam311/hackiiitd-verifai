"""Test configuration.

Ensures no real credentials or real database paths leak into the test suite.
All modules are imported AFTER these environment variables are set.
The environment variables set here take precedence over any .env file,
because pydantic-settings sources env vars before the env_file.
"""
import os

# --- Database: never touch a real file during tests ---
os.environ["VERIFAI_DATABASE_URL"] = "sqlite:///:memory:"

# --- Provider credentials: set to empty string so Settings() sees "not configured"
# regardless of whatever is in the developer's .env file.
# Tests that need a mock provider/LLM pass them directly to create_app().
for _var in (
    "OPENAI_API_KEY", "OPENAI_MODEL",
    "TINYFISH_API_KEY",
    "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
    "GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET",
):
    os.environ[_var] = ""


# Clear lru_cache on get_settings so the updated env vars take effect
# when any test module calls get_settings() or Settings().
def pytest_configure(config):
    try:
        from app.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass