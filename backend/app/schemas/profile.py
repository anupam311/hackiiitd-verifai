"""Profile schema — user's education, location, experience and interests.

Data-minimization principle: only the minimum fields needed for matching are stored.
The profile is never included in search results; only match-reason labels are exposed.
"""
from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """Fields the user can set. All are optional; a PATCH with an empty body is valid."""

    education: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    experience_years: int | None = Field(default=None, ge=0, le=50)
    interests: list[str] = Field(default_factory=list, max_length=20)


class ProfileResponse(BaseModel):
    """What the API returns — same fields as the update; all nullable."""

    education: str | None = None
    location: str | None = None
    experience_years: int | None = None
    interests: list[str] = Field(default_factory=list)


class MatchReason(BaseModel):
    """One explainable reason why this opportunity matches (or doesn't) for the user."""

    reason: str    # human-readable label, e.g. "Location match"
    detail: str    # e.g. "Your location 'Bengaluru' matches the opportunity location."
    positive: bool  # True = a match reason; False = a mismatch / gap


class MatchResponse(BaseModel):
    """Explainable match result for one opportunity."""

    opportunity_id: str
    reasons: list[MatchReason]
    overall: str  # "good_match" | "partial_match" | "no_match" | "unknown"
