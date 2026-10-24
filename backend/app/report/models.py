import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.enums import ClaimType, OpportunityStatus, RetrievalOutcome, SourceType, VerificationStatus
from app.schemas.source import SourceObservation
from app.verification.models import EvidenceRole, VerificationSummary


class EvidenceEntry(BaseModel):
    """Evidence for one claim, joined with the source it came from."""

    source_observation_id: str
    url: str
    domain: str
    source_type: SourceType
    retrieved_at: dt.datetime
    extracted_value: str
    normalized_value: str | None
    excerpt: str | None
    evidence_locator: str
    confidence: float
    is_authoritative: bool
    is_fresh: bool
    role: EvidenceRole


class ClaimReport(BaseModel):
    claim_type: ClaimType
    status: VerificationStatus
    normalized_value: str | None
    explanation: str
    next_step: str | None
    checked_at: dt.datetime
    stale: bool
    needs_review: bool
    evidence: list[EvidenceEntry] = Field(default_factory=list)


class VerificationReport(BaseModel):
    run_id: str
    opportunity_id: str
    generated_at: dt.datetime
    status: OpportunityStatus  # derived only from a confirmed application_status claim
    summary: VerificationSummary
    claims: list[ClaimReport]
    sources: list[SourceObservation]


class SourceSummary(BaseModel):
    observation_id: str
    url: str
    domain: str
    source_type: SourceType
    retrieved_at: dt.datetime
    retrieval_outcome: RetrievalOutcome
    is_authoritative: bool


class ComparisonCell(BaseModel):
    source_observation_id: str
    value: str | None  # the value as found on the page
    state: Literal["agrees", "differs", "ambiguous", "missing", "unavailable"]


class ComparisonRow(BaseModel):
    claim_type: ClaimType
    status: VerificationStatus
    agreement: Literal["agree", "partial", "conflict", "missing"]
    cells: list[ComparisonCell]


class ConflictValue(BaseModel):
    source_observation_id: str
    url: str
    domain: str
    source_type: SourceType
    retrieved_at: dt.datetime
    extracted_value: str


class ConflictCallout(BaseModel):
    claim_type: ClaimType
    status: VerificationStatus
    message: str
    values: list[ConflictValue]


class SourceComparison(BaseModel):
    opportunity_id: str
    run_id: str
    generated_at: dt.datetime
    sources: list[SourceSummary]  # official/employer/institution first
    rows: list[ComparisonRow]
    conflicts: list[ConflictCallout]
    warnings: list[str]