from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.main import create_app


def make_client() -> TestClient:
    app = create_app(Settings())

    class Body(BaseModel):
        n: int

    @app.post("/_t/validate")
    def validate(body: Body):
        return body

    @app.get("/_t/boom")
    def boom():
        raise RuntimeError("secret-internal-detail")

    return TestClient(app, raise_server_exceptions=False)


def assert_error_shape(resp, status, code):
    assert resp.status_code == status
    err = resp.json()["error"]
    assert set(err) == {"code", "message", "request_id"}
    assert err["code"] == code
    assert err["request_id"].startswith("req_")
    assert resp.headers["X-Request-ID"] == err["request_id"]


def test_health():
    r = make_client().get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok" and data["service"] == "verifai-api"
    assert "version" in data
    assert r.headers["X-Request-ID"].startswith("req_")


def test_not_found_uses_standard_shape():
    assert_error_shape(make_client().get("/nope"), 404, "NOT_FOUND")


def test_validation_error_uses_standard_shape_without_echoing_input():
    r = make_client().post("/_t/validate", json={"n": "private-text"})
    assert_error_shape(r, 400, "VALIDATION_ERROR")
    assert "private-text" not in r.text


def test_unexpected_error_hides_internals():
    r = make_client().get("/_t/boom")
    assert_error_shape(r, 500, "INTERNAL_ERROR")
    assert "secret-internal-detail" not in r.text


def test_docs_disabled_in_production():
    app = create_app(Settings(env="production"))
    assert TestClient(app).get("/docs").status_code == 404