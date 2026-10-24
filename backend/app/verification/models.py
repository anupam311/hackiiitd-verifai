import datetime as dt
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.enums import ClaimType, VerificationStatus
from app.schemas.source import SourceObservation


class EvidenceItem(BaseModel):
    """One extracted value tied to the observation it came from (input to the engine)."""

    claim_type: ClaimType
    extracted_value: str
    excerpt: str | None = None
    evidence_locator: str
    confidence: float = Field(ge=0.0, le=1.0)  # extraction confidence, not source credibility
    observation: SourceObservation
    extraction_method: str = ""
    schema_version: str = ""


class EvidenceRole(str, Enum):
    supports = "supports"
    discrepant = "discrepant"  # differs from the winning value; kept visible
    conflicting = "conflicting"  # one side of an unresolved conflict
    ambiguous = "ambiguous"  # could not be normalized, or low extraction confidence


class EvidenceAssessment(BaseModel):
    source_observation_id: str
    extracted_value: str
    normalized_value: str | None
    excerpt: str | None
    evidence_locator: str
    confidence: float
    is_certain: bool
    is_authoritative: bool
    is_fresh: bool
    role: EvidenceRole


class ClaimVerdict(BaseModel):
    claim_type: ClaimType
    status: VerificationStatus
    normalized_value: str | None
    explanation: str
    next_step: str | None = None
    checked_at: dt.datetime
    stale: bool = False
    needs_review: bool = False
    evidence: list[EvidenceAssessment] = Field(default_factory=list)


class VerificationSummary(BaseModel):
    total: int
    counts: dict[str, int]
    score_percent: float | None  # coverage score, NOT a probability
    discrepancies: int
    formula: str