import datetime as dt

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ensure_utc, utc_now
from app.schemas.enums import ClaimType, VerificationStatus


class Claim(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    opportunity_id: str = Field(min_length=1, max_length=64)
    claim_type: ClaimType
    normalized_value: str | None = Field(default=None, max_length=500)
    status: VerificationStatus = VerificationStatus.unverified
    explanation: str = Field(min_length=1, max_length=1000)  # every status needs a reason
    checked_at: dt.datetime = Field(default_factory=utc_now)

    _utc = field_validator("checked_at")(ensure_utc)


class ClaimEvidence(BaseModel):
    """Links a claim to an observation. `confidence` is EXTRACTION confidence, not source credibility."""

    claim_id: str = Field(min_length=1, max_length=64)
    source_observation_id: str = Field(min_length=1, max_length=64)
    extracted_value: str = Field(max_length=500)
    excerpt: str | None = Field(default=None, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_locator: str = Field(min_length=1, max_length=300)
    extraction_method: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(min_length=1, max_length=20)