"""Session authentication. Sessions are random tokens in an HttpOnly cookie; only their hash is stored."""
import hashlib
import re

from fastapi import HTTPException, Request

from app.schemas.common import utc_now

SESSION_COOKIE = "verifai_session"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def safe_next_path(value: str | None) -> str:
    """Only same-site relative paths are allowed after sign-in (prevents open redirects)."""
    if (not value or len(value) > 200 or not value.startswith("/") or value.startswith("//")
            or "\\" in value or re.search(r"[\x00-\x1f\x7f]", value) or "://" in value):
        return "/"
    return value


def current_user_id(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        user_id = request.app.state.store.get_session_user_id(hash_token(token), utc_now())
        if user_id:
            return user_id
    raise HTTPException(401, "Authentication required.")