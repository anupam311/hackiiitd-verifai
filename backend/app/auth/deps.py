"""Authentication boundary. B11 replaces the body with real session lookup; routes stay unchanged."""
from fastapi import HTTPException, Request


def current_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(401, "Authentication required.")
    return user_id