import asyncio
import datetime as dt
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth.deps import SESSION_COOKIE, hash_token, safe_next_path
from app.auth.models import ProviderIdentity
from app.auth.providers import AuthFlowError, GoogleProvider, pkce_challenge
from app.config import Settings
from app.main import create_app
from app.repositories.sqlite import SqliteStore
from app.routes.auth import STATE_COOKIE
from test_runs import deps, go  # B9 fixtures: seeds one opportunity

CLIENT_ID, SECRET = "test-client.apps.example", "test-client-secret"
REDIRECT = "http://localhost:8000/auth/google/callback"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)
DROP = object()


def make_token(nonce="n1", key=KEY, alg="RS256", **over):
    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "g-123", "iat": now,
              "exp": now + 600, "nonce": nonce, "email": "ann@example.com", "email_verified": True,
              "name": "Ann", "picture": "https://img.example.com/a.png", **over}
    claims = {k: v for k, v in claims.items() if v is not DROP}
    return jwt.encode(claims, key, algorithm=alg, headers={"kid": "k1"})


def transport(id_token=None, status=200, captured=None, raises=None, body=None):
    def handler(req: httpx.Request):
        if raises:
            raise raises
        if captured is not None:
            captured.append(parse_qs(req.content.decode()))
        return httpx.Response(status, json=body if body is not None else
                              ({"id_token": id_token, "access_token": "at"} if status == 200 else {"error": "x"}))
    return httpx.MockTransport(handler)


async def _pub(token):
    return KEY.public_key()


def google(**kw):
    return GoogleProvider(CLIENT_ID, SECRET, key_resolver=_pub, **kw)


def complete(p, nonce="n1"):
    return asyncio.run(p.complete(code="the-code", code_verifier="v" * 50, nonce=nonce, redirect_uri=REDIRECT))


# ---- provider ----
def test_authorization_url_has_pkce_state_nonce_and_no_secret():
    url = google().authorization_url(state="S", nonce="N", code_challenge=pkce_challenge("v" * 50), redirect_uri=REDIRECT)
    q = parse_qs(urlsplit(url).query)
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert q["state"] == ["S"] and q["nonce"] == ["N"] and q["code_challenge_method"] == ["S256"]
    assert q["response_type"] == ["code"] and q["scope"] == ["openid email profile"] and q["redirect_uri"] == [REDIRECT]
    assert q["code_challenge"] == [pkce_challenge("v" * 50)] and SECRET not in url


def test_complete_exchanges_code_server_side_and_returns_verified_identity():
    sent = []
    ident = complete(google(transport=transport(make_token(), captured=sent)))
    assert ident == ProviderIdentity("google", "g-123", "ann@example.com", True, "Ann", "https://img.example.com/a.png")
    form = sent[0]
    assert form["grant_type"] == ["authorization_code"] and form["code"] == ["the-code"]
    assert form["code_verifier"] == ["v" * 50] and form["client_secret"] == [SECRET] and form["redirect_uri"] == [REDIRECT]


@pytest.mark.parametrize("token", [
    make_token(nonce="other"), make_token(aud="someone-else"), make_token(iss="https://evil.example"),
    make_token(exp=int(time.time()) - 3600), make_token(sub=DROP), make_token(key=OTHER),
    jwt.encode({"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "x", "iat": 1, "exp": 4102444800,
                "nonce": "n1"}, key=None, algorithm="none"),
    make_token(key="hmac-secret-hmac-secret-hmac-secret-32", alg="HS256"), "not-a-jwt",
], ids=["wrong-nonce", "wrong-aud", "wrong-iss", "expired", "no-sub", "wrong-key", "alg-none", "hs256", "garbage"])
def test_bad_id_tokens_are_rejected(token):
    with pytest.raises(AuthFlowError) as e:
        complete(google(transport=transport(token)))
    assert e.value.code == "invalid_id_token"


def test_token_endpoint_failures():
    for kw, code in [({"status": 400}, "token_exchange_failed"), ({"body": {"no": "token"}}, "token_exchange_failed"),
                     ({"raises": httpx.ConnectError("boom")}, "network_error")]:
        with pytest.raises(AuthFlowError) as e:
            complete(google(transport=transport(make_token(), **kw)))
        assert e.value.code == code and "boom" not in str(e.value)


def test_unverified_or_missing_email_and_unsafe_avatar_are_handled():
    assert complete(google(transport=transport(make_token(email_verified="true")))).email_verified is True
    assert complete(google(transport=transport(make_token(email_verified=False)))).email_verified is False
    no_email = complete(google(transport=transport(make_token(email=DROP, email_verified=True))))
    assert no_email.email is None and no_email.email_verified is False
    assert complete(google(transport=transport(make_token(picture="http://insecure.example/a.png")))).avatar_url is None
    assert complete(google(transport=transport(make_token(name="Bo\x00b\n")))).display_name == "Bob"


@pytest.mark.parametrize("given,expected", [
    ("/saved", "/saved"), ("/a?b=1", "/a?b=1"), (None, "/"), ("", "/"), ("//evil.example", "/"),
    ("https://evil.example", "/"), ("/\\evil.example", "/"), ("javascript:alert(1)", "/"),
    ("/x\r\nSet-Cookie: a=b", "/"), ("/redirect?u=https://evil.example", "/"), ("/" + "a" * 300, "/"),
])
def test_next_path_only_allows_same_site_paths(given, expected):
    assert safe_next_path(given) == expected


# ---- flows ----
class FakeProvider:
    name = "google"

    def __init__(self, identity=None, error=None):
        self.identity = identity or ProviderIdentity("google", "g-1", "ann@example.com", True, "Ann", None)
        self.error, self.calls = error, []

    def authorization_url(self, *, state, nonce, code_challenge, redirect_uri):
        return f"https://idp.example/auth?state={state}&nonce={nonce}&cc={code_challenge}"

    async def complete(self, *, code, code_verifier, nonce, redirect_uri):
        self.calls.append(dict(code=code, verifier=code_verifier, nonce=nonce, redirect_uri=redirect_uri))
        if self.error:
            raise AuthFlowError(self.error)
        return self.identity


def make(provider=None, store=None, providers=None, **settings):
    store = store or SqliteStore(":memory:")
    providers = {"google": provider} if provider else (providers or {})
    app = create_app(Settings(_env_file=None, **settings), store=store, oauth_providers=providers)
    return TestClient(app, follow_redirects=False), store


def start(c, next_="/"):
    r = c.get("/auth/google/login", params={"next": next_})
    assert r.status_code == 302
    return parse_qs(urlsplit(r.headers["location"]).query)["state"][0], r


def cookie_line(resp, name):
    return next(h for h in resp.headers.get_list("set-cookie") if h.startswith(name + "="))


def login(c, next_="/"):
    state, _ = start(c, next_)
    return c.get("/auth/google/callback", params={"code": "c", "state": state})


def error_of(resp):
    assert resp.status_code == 302
    loc = urlsplit(resp.headers["location"])
    assert loc.path == "/login"
    return parse_qs(loc.query)["error"][0]


def test_unconfigured_and_unknown_providers():
    c, _ = make()
    assert c.get("/auth/google/login").status_code == 503
    assert c.get("/auth/google/login").json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert c.get("/auth/nope/login").status_code == 404
    assert c.get("/auth/Bad1/login").status_code == 400


def test_login_redirects_with_state_and_binds_it_to_the_browser():
    prov = FakeProvider()
    c, store = make(prov)
    state, r = start(c, "/saved")
    line = cookie_line(r, STATE_COOKIE).lower()
    assert f"{STATE_COOKIE}={state}".lower() in line and "httponly" in line and "samesite=lax" in line
    assert "path=/auth" in line and "max-age=600" in line and "secure" not in line  # http in dev
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert len(q["state"][0]) >= 40 and q["nonce"][0] != q["state"][0] and q["cc"][0]


def test_successful_login_creates_session_cookie_and_redirects_to_frontend():
    prov = FakeProvider()
    c, store = make(prov, frontend_url="http://localhost:3000/")
    r = login(c, "/saved")
    assert r.status_code == 302 and r.headers["location"] == "http://localhost:3000/saved"
    line = cookie_line(r, SESSION_COOKIE).lower()
    assert "httponly" in line and "samesite=lax" in line and "path=/" in line and f"max-age={7 * 86400}" in line
    assert prov.calls[0]["redirect_uri"] == REDIRECT and prov.calls[0]["code"] == "c"
    me = c.get("/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "ann@example.com" and me.json()["providers"] == ["google"]
    assert set(me.json()) == {"id", "email", "email_verified", "display_name", "avatar_url", "created_at", "providers"}
    assert STATE_COOKIE not in c.cookies  # the state cookie is cleared


def test_secure_flag_follows_https_public_url():
    c, _ = make(FakeProvider(), public_base_url="https://api.example.com")
    state, r = start(c)
    assert "secure" in cookie_line(r, STATE_COOKIE).lower()
    c.cookies.clear()
    c.cookies.set(STATE_COOKIE, state, path="/auth")
    ok = c.get("/auth/google/callback", params={"code": "c", "state": state})
    assert "secure" in cookie_line(ok, SESSION_COOKIE).lower()


def test_session_token_is_stored_only_as_a_hash():
    c, store = make(FakeProvider())
    login(c)
    raw = c.cookies.get(SESSION_COOKIE)
    rows = store._conn.execute("SELECT token_hash FROM sessions").fetchall()
    assert rows == [(hash_token(raw),)] and raw not in rows[0][0]
    stored_state = store._conn.execute("SELECT count(*) FROM oauth_states").fetchone()[0]
    assert stored_state == 0  # consumed


def test_same_identity_maps_to_same_user_and_new_subject_to_new_user():
    prov = FakeProvider()
    c, store = make(prov)
    login(c)
    first = c.get("/auth/me").json()["id"]
    login(c)
    assert c.get("/auth/me").json()["id"] == first
    prov.identity = ProviderIdentity("google", "g-2", "bob@example.com", True, "Bob", None)
    c2 = TestClient(c.app, follow_redirects=False)
    login(c2)
    assert c2.get("/auth/me").json()["id"] != first
    assert store._conn.execute("SELECT count(*) FROM users").fetchone()[0] == 2


def test_unverified_email_is_not_stored():
    prov = FakeProvider(ProviderIdentity("google", "g-9", "x@example.com", False, None, None))
    c, _ = make(prov)
    login(c)
    me = c.get("/auth/me").json()
    assert me["email"] is None and me["email_verified"] is False


def test_callback_rejects_missing_mismatched_reused_and_expired_state():
    prov = FakeProvider()
    c, store = make(prov)
    state, _ = start(c)
    # no cookie
    c.cookies.clear()
    assert error_of(c.get("/auth/google/callback", params={"code": "c", "state": state})) == "invalid_state"
    # cookie for a different flow
    c.cookies.set(STATE_COOKIE, "someone-elses-state", path="/auth")
    assert error_of(c.get("/auth/google/callback", params={"code": "c", "state": state})) == "invalid_state"
    # missing state param
    assert error_of(c.get("/auth/google/callback", params={"code": "c"})) == "invalid_state"
    # valid once, then single-use
    c.cookies.set(STATE_COOKIE, state, path="/auth")
    assert c.get("/auth/google/callback", params={"code": "c", "state": state}).headers["location"].endswith("/")
    c.cookies.set(STATE_COOKIE, state, path="/auth")
    assert error_of(c.get("/auth/google/callback", params={"code": "c", "state": state})) == "invalid_state"
    # expired
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    store.save_oauth_state(hash_token("old"), "google", "n", "v", "/", past)
    c.cookies.set(STATE_COOKIE, "old", path="/auth")
    assert error_of(c.get("/auth/google/callback", params={"code": "c", "state": "old"})) == "invalid_state"
    assert len(prov.calls) == 1  # the provider was only contacted for the one valid callback


def test_failed_flows_redirect_with_fixed_error_codes_and_create_no_session():
    c, store = make(FakeProvider(error="invalid_id_token"))
    assert error_of(login(c)) == "oauth_failed"
    assert c.get("/auth/me").status_code == 401 and store._conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    c2, _ = make(FakeProvider())
    state, _ = start(c2)
    assert error_of(c2.get("/auth/google/callback", params={"error": "access_denied", "state": state})) == "access_denied"
    state, _ = start(c2)
    assert error_of(c2.get("/auth/google/callback", params={"error": "<script>", "state": state})) == "oauth_failed"
    state, _ = start(c2)
    assert error_of(c2.get("/auth/google/callback", params={"state": state})) == "oauth_failed"  # no code


def test_sign_in_replaces_an_existing_session():
    c, store = make(FakeProvider())
    login(c)
    old = c.cookies.get(SESSION_COOKIE)
    login(c)
    new = c.cookies.get(SESSION_COOKIE)
    assert old != new and store.get_session_user_id(hash_token(old), dt.datetime.now(dt.timezone.utc)) is None


def test_logout_deletes_the_session_server_side_and_is_idempotent():
    c, store = make(FakeProvider())
    login(c)
    stolen = c.cookies.get(SESSION_COOKIE)
    r = c.post("/auth/logout")
    assert r.status_code == 204 and "max-age=0" in cookie_line(r, SESSION_COOKIE).lower()
    c.cookies.set(SESSION_COOKIE, stolen)  # a copied cookie must not work any more
    assert c.get("/auth/me").status_code == 401
    assert make()[0].post("/auth/logout").status_code == 204


def test_expired_session_is_rejected_and_removed():
    c, store = make(FakeProvider())
    login(c)
    token = c.cookies.get(SESSION_COOKIE)
    store._conn.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00.000000Z'")
    r = c.get("/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
    assert store._conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_protected_routes_use_the_real_session_without_overrides():
    store = SqliteStore(":memory:")
    _, run = go(deps(store=store))
    oid = run.opportunities[0].id
    prov = FakeProvider()
    a, _ = make(prov, store=store)
    assert a.put(f"/api/v1/saved/{oid}").status_code == 401
    login(a)
    assert a.put(f"/api/v1/saved/{oid}").status_code == 200
    assert [x["opportunity"]["id"] for x in a.get("/api/v1/saved").json()] == [oid]
    prov.identity = ProviderIdentity("google", "g-2", None, False, None, None)
    b = TestClient(a.app, follow_redirects=False)
    login(b)
    assert b.get("/api/v1/saved").json() == []  # another user sees nothing


def test_origin_guard_blocks_cross_site_writes_but_allows_known_origins_and_non_browsers():
    c, _ = make(FakeProvider())
    login(c)
    evil = {"Origin": "https://evil.example"}
    r = c.post("/auth/logout", headers=evil)
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN" and r.json()["error"]["request_id"]
    assert c.get("/auth/me").status_code == 200  # the blocked logout did nothing
    assert c.put("/api/v1/saved/anything", headers=evil).status_code == 403
    assert c.post("/auth/logout", headers={"Origin": "http://localhost:3000"}).status_code == 204
    assert c.post("/auth/logout").status_code == 204  # no Origin header (curl, server-side)


def test_no_secrets_leak_in_any_response():
    c, _ = make(FakeProvider())
    seen = [c.get("/auth/google/login"), login(c), c.get("/auth/me")]
    for r in seen:
        assert SECRET not in r.text and SECRET not in str(r.headers)


def test_full_flow_with_the_real_google_provider_and_mocked_google():
    sent = []
    holder = {}

    def handler(req: httpx.Request):
        form = parse_qs(req.content.decode())
        sent.append(form)
        return httpx.Response(200, json={"id_token": make_token(nonce=holder["nonce"], sub="g-777"), "access_token": "x"})

    prov = GoogleProvider(CLIENT_ID, SECRET, transport=httpx.MockTransport(handler), key_resolver=_pub)
    c, _ = make(prov)
    r = c.get("/auth/google/login", params={"next": "/saved"})
    q = parse_qs(urlsplit(r.headers["location"]).query)
    holder["nonce"] = q["nonce"][0]
    cb = c.get("/auth/google/callback", params={"code": "real-code", "state": q["state"][0]})
    assert cb.headers["location"] == "http://localhost:3000/saved"
    assert pkce_challenge(sent[0]["code_verifier"][0]) == q["code_challenge"][0]  # PKCE verifier matches
    me = c.get("/auth/me").json()
    assert me["display_name"] == "Ann" and me["email"] == "ann@example.com"