import datetime as dt
from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ProviderIdentity:
    """What a provider tells us about a signed-in person, after verification."""

    provider: str
    subject: str  # stable provider-side id; never the email
    email: str | None
    email_verified: bool
    display_name: str | None = None
    avatar_url: str | None = None


class User(BaseModel):
    id: str
    email: str | None  # only stored when the provider verified it
    email_verified: bool
    display_name: str | None
    avatar_url: str | None
    created_at: dt.datetime
    providers: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class OAuthState:
    provider: str
    nonce: str
    code_verifier: str
    next_path: str