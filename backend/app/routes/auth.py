import hmac
import logging
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.auth.deps import SESSION_COOKIE, current_user_id, hash_token, safe_next_path
from app.auth.models import User
from app.auth.providers import AuthFlowError, pkce_challenge
from app.config import Settings
from app.schemas.common import utc_now

logger = logging.getLogger("verifai.auth")
router = APIRouter(prefix="/auth", tags=["auth"])
STATE_COOKIE = "verifai_oauth_state"
KNOWN_PROVIDERS = {"google", "github"}
Provider = Annotated[str, Path(pattern="^[a-z]{1,20}$")]


def _secure(settings: Settings) -> bool:
    return settings.public_base_url.startswith("https://")


def _provider(request: Request, name: str):
    if name not in KNOWN_PROVIDERS:
        raise HTTPException(404, "Unknown sign-in provider.")
    provider = request.app.state.oauth_providers.get(name)
    if provider is None:
        raise HTTPException(503, f"Sign-in with {name.title()} is not configured on this server.")
    return provider


def _redirect_uri(settings: Settings, name: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/auth/{name}/callback"


def _fail(settings: Settings, code: str) -> RedirectResponse:
    # Fixed error vocabulary only: nothing from the provider is reflected to the browser.
    resp = RedirectResponse(f"{settings.frontend_url.rstrip('/')}/login?error={code}", status_code=302)
    resp.delete_cookie(STATE_COOKIE, path="/auth", secure=_secure(settings), httponly=True, samesite="lax")
    return resp


@router.get("/{provider}/login")
def login(provider: Provider, request: Request, next_: Annotated[str, Query(alias="next", max_length=300)] = "/"):
    st = request.app.state
    p = _provider(request, provider)
    now = utc_now()
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    st.store.purge_expired_auth(now)
    st.store.save_oauth_state(hash_token(state), provider, nonce, verifier, safe_next_path(next_),
                              now + timedelta(minutes=10))
    url = p.authorization_url(state=state, nonce=nonce, code_challenge=pkce_challenge(verifier),
                              redirect_uri=_redirect_uri(st.settings, provider))
    resp = RedirectResponse(url, status_code=302)
    # The cookie binds the flow to this browser: a callback without it is rejected (login CSRF).
    resp.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax",
                    secure=_secure(st.settings), path="/auth")
    return resp


@router.get("/{provider}/callback")
async def callback(provider: Provider, request: Request,
                   code: Annotated[str | None, Query(max_length=2048)] = None,
                   state: Annotated[str | None, Query(max_length=256)] = None,
                   error: Annotated[str | None, Query(max_length=100)] = None):
    st = request.app.state
    p = _provider(request, provider)
    cookie = request.cookies.get(STATE_COOKIE)
    if not state or not cookie or not hmac.compare_digest(cookie.encode(), state.encode()):
        return _fail(st.settings, "invalid_state")
    now = utc_now()
    rec = st.store.pop_oauth_state(hash_token(state), now)  # single use, even on failure below
    if rec is None or rec.provider != provider:
        return _fail(st.settings, "invalid_state")
    if error:
        return _fail(st.settings, "access_denied" if error == "access_denied" else "oauth_failed")
    if not code:
        return _fail(st.settings, "oauth_failed")
    try:
        identity = await p.complete(code=code, code_verifier=rec.code_verifier, nonce=rec.nonce,
                                    redirect_uri=_redirect_uri(st.settings, provider))
    except AuthFlowError as exc:
        logger.warning("oauth failure provider=%s code=%s", provider, exc.code)
        return _fail(st.settings, "oauth_failed")

    user = st.store.find_or_create_user(identity, now)
    old = request.cookies.get(SESSION_COOKIE)
    if old:  # new session on every sign-in: no session fixation
        st.store.delete_session(hash_token(old))
    token = secrets.token_urlsafe(32)
    ttl = timedelta(days=st.settings.session_ttl_days)
    st.store.create_session(hash_token(token), user.id, now, now + ttl)
    resp = RedirectResponse(f"{st.settings.frontend_url.rstrip('/')}{rec.next_path}", status_code=302)
    resp.set_cookie(SESSION_COOKIE, token, max_age=int(ttl.total_seconds()), httponly=True, samesite="lax",
                    secure=_secure(st.settings), path="/")
    resp.delete_cookie(STATE_COOKIE, path="/auth", secure=_secure(st.settings), httponly=True, samesite="lax")
    return resp


@router.post("/logout", status_code=204)
def logout(request: Request):
    """Idempotent. Deletes the server-side session, so a copied cookie stops working too."""
    st = request.app.state
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        st.store.delete_session(hash_token(token))
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE, path="/", secure=_secure(st.settings), httponly=True, samesite="lax")
    return resp


@router.get("/me", response_model=User)
def me(request: Request, user_id: str = Depends(current_user_id)):
    user = request.app.state.store.get_user(user_id)
    if user is None:
        raise HTTPException(401, "Authentication required.")
    return user