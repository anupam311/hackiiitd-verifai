"""B15 + B16 tests: production settings, security headers, readiness probe,
body-size guard, error hardening, and security boundary checks.
"""
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.main import create_app
from app.repositories.memory import InMemoryStore


# ── helpers ────────────────────────────────────────────────────────────────

def make_client(store=None, **setting_overrides) -> TestClient:
    store = store or InMemoryStore()
    app = create_app(Settings(_env_file=None, **setting_overrides), store=store)

    class Body(BaseModel):
        n: int

    @app.post("/_t/validate")
    def validate_body(body: Body):
        return body

    @app.get("/_t/boom")
    def boom():
        raise RuntimeError("secret-internal-detail")

    return TestClient(app, raise_server_exceptions=False)


def assert_error(resp, status, code):
    assert resp.status_code == status, f"expected {status}, got {resp.status_code}: {resp.text}"
    err = resp.json()["error"]
    assert set(err) == {"code", "message", "request_id"}
    assert err["code"] == code
    assert err["request_id"].startswith("req_")
    assert resp.headers["X-Request-ID"] == err["request_id"]


# ── B15: production settings ────────────────────────────────────────────────

def test_docs_disabled_in_production():
    app = create_app(Settings(_env_file=None, env="production"), store=InMemoryStore())
    with TestClient(app) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404


def test_docs_available_in_development():
    app = create_app(Settings(_env_file=None, env="development"), store=InMemoryStore())
    with TestClient(app) as c:
        assert c.get("/docs").status_code == 200
        assert c.get("/openapi.json").status_code == 200


def test_health_liveness_returns_version():
    r = make_client().get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok" and data["service"] == "verifai-api"
    assert "version" in data


def test_readiness_probe_ok_with_in_memory_store():
    c = make_client()
    r = c.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready" and data["service"] == "verifai-api"


def test_readiness_probe_fails_gracefully_on_broken_store():
    """If the store raises, /health/ready returns 503 with the standard error shape."""
    class BrokenStore(InMemoryStore):
        def list_opportunities(self, **kw):
            raise OSError("db gone")

    store = BrokenStore()
    app = create_app(Settings(_env_file=None), store=store)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/health/ready")
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "SERVICE_UNAVAILABLE" and "Database" in err["message"]


def test_config_log_level_validation():
    from pydantic import ValidationError
    with pytest.raises((ValidationError, ValueError)):
        Settings(_env_file=None, log_level="VERBOSE")


def test_config_trusted_host_list_empty_by_default():
    assert Settings(_env_file=None).trusted_host_list == []


def test_config_trusted_host_list_parsed():
    s = Settings(_env_file=None, trusted_hosts="api.example.com, localhost")
    assert s.trusted_host_list == ["api.example.com", "localhost"]


def test_trusted_host_middleware_rejects_unknown_host(monkeypatch):
    """When VERIFAI_TRUSTED_HOSTS is set, requests to an unlisted host get 400."""
    app = create_app(
        Settings(_env_file=None, trusted_hosts="api.example.com"),
        store=InMemoryStore()
    )
    with TestClient(app, raise_server_exceptions=False) as c:
        # TestClient sends Host: testserver by default
        r = c.get("/health")
        assert r.status_code == 400  # TrustedHostMiddleware returns 400

    # Correct host works fine
    with TestClient(app, base_url="http://api.example.com", raise_server_exceptions=False) as c:
        r = c.get("/health")
        assert r.status_code == 200


# ── B15: body-size guard ───────────────────────────────────────────────────

def test_body_size_guard_rejects_oversized_payload():
    """Content-Length above the configured limit → 413 PAYLOAD_TOO_LARGE."""
    app = create_app(Settings(_env_file=None, max_request_body_bytes=100), store=InMemoryStore())
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.post(
            "/api/v1/discovery/search",
            content=b"x" * 200,
            headers={"Content-Type": "application/json", "Content-Length": "200"},
        )
    assert r.status_code == 413
    err = r.json()["error"]
    assert err["code"] == "PAYLOAD_TOO_LARGE"


def test_body_size_guard_allows_normal_payload():
    c = make_client()
    r = c.get("/health")
    assert r.status_code == 200  # no Content-Length issue


# ── B15: security headers ──────────────────────────────────────────────────

def test_security_headers_present_on_every_response():
    c = make_client()
    for path in ("/health", "/api/v1/opportunities"):
        r = c.get(path)
        assert r.headers.get("X-Content-Type-Options") == "nosniff", path
        assert r.headers.get("X-Frame-Options") == "DENY", path
        assert "strict-origin" in r.headers.get("Referrer-Policy", ""), path
        assert "Permissions-Policy" in r.headers, path


def test_auth_endpoints_have_no_cache_header():
    c = make_client()
    # Even a non-existent provider returns a response with Cache-Control set
    r = c.get("/auth/google/login")
    assert "no-store" in r.headers.get("Cache-Control", "").lower()


def test_request_id_header_on_every_response():
    c = make_client()
    for path in ("/health", "/api/v1/opportunities", "/nope"):
        r = c.get(path)
        assert r.headers.get("X-Request-ID", "").startswith("req_"), path


# ── B16: error hardening ───────────────────────────────────────────────────

def test_validation_error_is_400_not_422():
    """FastAPI would normally return 422 for body validation; we normalize to 400."""
    c = make_client()
    r = c.post("/_t/validate", json={"n": "not-a-number"})
    assert_error(r, 400, "VALIDATION_ERROR")


def test_unexpected_error_hides_internals_and_does_not_echo_exception():
    c = make_client()
    r = c.get("/_t/boom")
    assert_error(r, 500, "INTERNAL_ERROR")
    assert "secret-internal-detail" not in r.text
    assert "RuntimeError" not in r.text


def test_not_found_uses_standard_error_shape():
    assert_error(make_client().get("/does-not-exist"), 404, "NOT_FOUND")


def test_method_not_allowed_uses_standard_error_shape():
    """DELETE on a GET-only endpoint should get a standard error body."""
    c = make_client()
    r = c.delete("/health")
    # FastAPI returns 405; we normalise it to a standard shape
    assert r.status_code == 405
    err = r.json().get("error")
    assert err is not None and err["code"] == "METHOD_NOT_ALLOWED"


def test_overlong_path_param_is_400_validation_error():
    c = make_client()
    r = c.get("/api/v1/opportunities/" + "x" * 65)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_origin_guard_blocks_cross_origin_writes_with_standard_shape():
    c = make_client()
    r = c.post("/auth/logout", headers={"Origin": "https://evil.example"})
    assert_error(r, 403, "FORBIDDEN")


def test_origin_guard_allows_same_origin_and_no_origin():
    c = make_client()
    assert c.post("/auth/logout").status_code == 204           # no Origin header
    assert c.post("/auth/logout",
                  headers={"Origin": "http://localhost:3000"}).status_code == 204


# ── B16: no secrets in any response ───────────────────────────────────────

def test_no_secret_in_error_responses():
    """Internal exception messages must never appear in API responses."""
    c = make_client()
    r = c.get("/_t/boom")
    assert "secret-internal-detail" not in r.text


# ── B16: CORS configuration ────────────────────────────────────────────────

def test_cors_preflight_from_allowed_origin():
    c = make_client()
    r = c.options(
        "/api/v1/opportunities",
        headers={"Origin": "http://localhost:3000",
                 "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"


def test_cors_preflight_from_disallowed_origin():
    c = make_client()
    r = c.options(
        "/api/v1/opportunities",
        headers={"Origin": "https://evil.example",
                 "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("Access-Control-Allow-Origin") is None
