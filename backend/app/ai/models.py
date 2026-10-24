"""Wire models (what the LLM must return) and validated domain output."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import ClaimType, OpportunityCategory

ClaimTypeLiteral = Literal[tuple(c.value for c in ClaimType)]  # type: ignore[valid-type]


class WireFact(BaseModel):
    """No length/range constraints and no defaults: keeps the JSON schema valid for strict mode.
    Real validation happens afterwards in extraction.py."""

    model_config = ConfigDict(extra="forbid")
    claim_type: ClaimTypeLiteral
    extracted_value: str
    excerpt: str | None
    confidence: float


class WirePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opportunity_title: str | None
    opportunity_category: str | None
    facts: list[WireFact]


class ExtractedFact(BaseModel):
    """A validated, grounded fact. The verification engine (B7) turns these into claim evidence."""

    claim_type: ClaimType
    extracted_value: str = Field(min_length=1, max_length=500)
    excerpt: str = Field(min_length=1, max_length=300)
    evidence_locator: str = Field(min_length=1, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)
    source_observation_id: str
    extraction_method: str
    schema_version: str


class ExtractionResult(BaseModel):
    facts: list[ExtractedFact] = Field(default_factory=list)
    opportunity_title: str | None = None
    opportunity_category: OpportunityCategory | None = None
    dropped: list[str] = Field(default_factory=list)  # reasons only, never page content
    truncated: bool = False