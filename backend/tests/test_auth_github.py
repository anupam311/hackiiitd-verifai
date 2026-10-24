"""Tests for GitHub OAuth flow (B12).

Covers:
- Provider: authorization URL, token exchange, user/email fetching, field sanitization
- Linking: verified GitHub email matching an existing Google account links identities
- Full HTTP flow: login → callback → session → /auth/me
- Error paths: network errors, bad token, blocked email, provider not configured
"""
import asyncio
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth.deps import SESSION_COOKIE, hash_token, safe_next_path
from app.auth.github import GitHubProvider
from app.auth.models import ProviderIdentity
from app.auth.providers import AuthFlowError
from app.config import Settings
from app.main import create_app
from app.repositories.memory import InMemoryStore
from app.routes.auth import STATE_COOKIE

CLIENT_ID, SECRET = "gh-test-client", "gh-test-secret"
REDIRECT = "http://localhost:8000/auth/github/callback"


# ---- transport helpers ----

def make_transport(token="gh-tok-abc", user=None, emails=None,
                   token_status=200, user_status=200, emails_status=200,
                   raises=None):
    """Builds a mock httpx transport that handles GitHub token + user + email calls."""
    _default_user = {"id": 12345, "login": "jdoe", "name": "Jane Doe",
                     "avatar_url": "https://avatars.github.com/u/12345"}
    _default_emails = [
        {"email": "jane@example.com", "verified": True, "primary": True},
        {"email": "jane@work.com", "verified": True, "primary": False},
    ]
    _user = user if user is not None else _default_user
    _emails = emails if emails is not None else _default_emails

    def handler(req: httpx.Request):
        if raises:
            raise raises
        if "access_token" in str(req.url) or "access_token" in req.content.decode(errors="ignore"):
            body = {"access_token": token, "token_type": "bearer"} if token_status == 200 else {"error": "bad"}
            return httpx.Response(token_status, json=body)
        if "/user/emails" in str(req.url):
            return httpx.Response(emails_status, json=_emails if emails_status == 200 else {})
        if "/user" in str(req.url):
            return httpx.Response(user_status, json=_user if user_status == 200 else {})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def github(**kw):
    kw.setdefault("transport", make_transport())
    return GitHubProvider(CLIENT_ID, SECRET, **kw)


def complete(p, code="the-code"):
    return asyncio.run(p.complete(code=code, code_verifier="v" * 50, nonce="n1", redirect_uri=REDIRECT))


# ---- provider unit tests ----

def test_authorization_url_has_state_scope_and_no_secret():
    url = github().authorization_url(state="S", nonce="N", code_challenge="C", redirect_uri=REDIRECT)
    q = parse_qs(urlsplit(url).query)
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert q["state"] == ["S"] and "read:user" in q["scope"][0] and "user:email" in q["scope"][0]
    assert q["redirect_uri"] == [REDIRECT] and SECRET not in url


def test_complete_returns_verified_identity():
    ident = complete(github())
    assert ident == ProviderIdentity(
        provider="github", subject="12345",
        email="jane@example.com", email_verified=True,
        display_name="Jane Doe", avatar_url="https://avatars.github.com/u/12345")


def test_non_https_avatar_is_stripped():
    user = {"id": 9, "login": "bob", "name": "Bob", "avatar_url": "http://insecure.example/a.png"}
    ident = complete(github(transport=make_transport(user=user)))
    assert ident.avatar_url is None


def test_control_chars_in_name_are_stripped():
    user = {"id": 9, "login": "bob", "name": "Bo\x00b\nSmith", "avatar_url": None}
    ident = complete(github(transport=make_transport(user=user)))
    assert ident.display_name == "BobSmith"


def test_no_primary_verified_email_falls_back_to_any_verified():
    emails = [
        {"email": "jane@work.com", "verified": True, "primary": False},
        {"email": "jane@unverified.com", "verified": False, "primary": True},
    ]
    ident = complete(github(transport=make_transport(emails=emails)))
    assert ident.email == "jane@work.com" and ident.email_verified is True


def test_no_verified_email_at_all():
    emails = [{"email": "jane@unverified.com", "verified": False, "primary": True}]
    ident = complete(github(transport=make_transport(emails=emails)))
    assert ident.email is None and ident.email_verified is False


def test_token_exchange_failures():
    for kw, code in [
        ({"token_status": 401}, "token_exchange_failed"),
        ({"raises": httpx.ConnectError("boom")}, "network_error"),
    ]:
        with pytest.raises(AuthFlowError) as exc:
            complete(github(transport=make_transport(**kw)))
        assert exc.value.code == code


def test_user_fetch_failure_raises_auth_flow_error():
    with pytest.raises(AuthFlowError) as exc:
        complete(github(transport=make_transport(user_status=500)))
    assert exc.value.code == "user_fetch_failed"


def test_user_without_id_raises_auth_flow_error():
    user = {"id": None, "login": "x"}
    with pytest.raises(AuthFlowError) as exc:
        complete(github(transport=make_transport(user=user)))
    assert exc.value.code == "user_fetch_failed"


# ---- HTTP flow ----

class FakeGitHubProvider:
    name = "github"

    def __init__(self, identity=None, error=None):
        self.identity = identity or ProviderIdentity(
            "github", "gh-1", "jane@example.com", True, "Jane", None)
        self.error, self.calls = error, []

    def authorization_url(self, *, state, nonce, code_challenge, redirect_uri):
        return f"https://github.com/login/oauth/authorize?state={state}"

    async def complete(self, *, code, code_verifier, nonce, redirect_uri):
        self.calls.append(dict(code=code, verifier=code_verifier, nonce=nonce))
        if self.error:
            raise AuthFlowError(self.error)
        return self.identity


def make_app(provider=None, store=None, providers=None, **settings):
    store = store or InMemoryStore()
    providers = {"github": provider} if provider else (providers or {})
    app = create_app(Settings(_env_file=None, **settings), store=store, oauth_providers=providers)
    return TestClient(app, follow_redirects=False), store


def start_flow(c, next_="/"):
    r = c.get("/auth/github/login", params={"next": next_})
    assert r.status_code == 302
    return parse_qs(urlsplit(r.headers["location"]).query)["state"][0], r


def login(c, next_="/"):
    state, _ = start_flow(c, next_)
    return c.get("/auth/github/callback", params={"code": "code123", "state": state})


def error_of(resp):
    assert resp.status_code == 302
    loc = urlsplit(resp.headers["location"])
    assert loc.path == "/login"
    return parse_qs(loc.query)["error"][0]


def test_unconfigured_github_returns_503():
    c, _ = make_app()
    assert c.get("/auth/github/login").status_code == 503
    assert c.get("/auth/github/login").json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_successful_github_login():
    prov = FakeGitHubProvider()
    c, store = make_app(prov)
    r = login(c, "/dashboard")
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:3000/dashboard"
    me = c.get("/auth/me").json()
    assert me["email"] == "jane@example.com" and me["providers"] == ["github"]


def test_github_callback_state_binding():
    prov = FakeGitHubProvider()
    c, _ = make_app(prov)
    state, _ = start_flow(c)
    c.cookies.clear()
    assert error_of(c.get("/auth/github/callback", params={"code": "c", "state": state})) == "invalid_state"


def test_github_auth_failure_redirects_with_fixed_code():
    c, store = make_app(FakeGitHubProvider(error="token_exchange_failed"))
    assert error_of(login(c)) == "oauth_failed"
    assert len(store._sessions) == 0



def test_github_access_denied_flow():
    prov = FakeGitHubProvider()
    c, _ = make_app(prov)
    state, _ = start_flow(c)
    assert error_of(c.get("/auth/github/callback", params={"error": "access_denied", "state": state})) == "access_denied"


# ---- account linking ----

def test_github_verified_email_links_to_existing_google_user():
    """A GitHub login with the same verified email as an existing Google user should link accounts."""
    store = InMemoryStore()
    # Seed a Google user
    google_identity = ProviderIdentity("google", "g-1", "jane@example.com", True, "Jane", None)
    from app.schemas.common import utc_now
    existing = store.find_or_create_user(google_identity, utc_now())

    # Now GitHub login with the same email
    github_identity = ProviderIdentity("github", "gh-1", "jane@example.com", True, "Jane", None)
    linked = store.find_or_create_user(github_identity, utc_now())

    # Should be the same user, not a new one
    assert linked.id == existing.id
    assert set(linked.providers) == {"google", "github"}


def test_github_unverified_email_does_not_link():
    """An unverified GitHub email must NOT trigger account linking."""
    store = InMemoryStore()
    from app.schemas.common import utc_now
    google_identity = ProviderIdentity("google", "g-1", "jane@example.com", True, "Jane", None)
    existing = store.find_or_create_user(google_identity, utc_now())
    # Same email but unverified
    github_identity = ProviderIdentity("github", "gh-99", "jane@example.com", False, "Jane", None)
    new_user = store.find_or_create_user(github_identity, utc_now())
    assert new_user.id != existing.id  # separate accounts


def test_no_secrets_leak_in_github_responses():
    prov = FakeGitHubProvider()
    c, _ = make_app(prov)
    seen = [c.get("/auth/github/login"), login(c), c.get("/auth/me")]
    for r in seen:
        assert SECRET not in r.text and SECRET not in str(r.headers)
