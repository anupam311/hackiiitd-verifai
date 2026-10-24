import datetime as dt
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ensure_utc, validate_http_url
from app.schemas.enums import Freshness, RetrievalOutcome, SourceType


class SourceObservation(BaseModel):
    """One time-stamped look at one URL. A failed retrieval is still an observation."""

    id: str = Field(min_length=1, max_length=64)
    opportunity_id: str | None = None  # may be unknown until extraction links it
    url: str
    domain: str = Field(min_length=1, max_length=255)
    source_type: SourceType = SourceType.other
    retrieved_at: dt.datetime
    http_status: int | None = Field(default=None, ge=100, le=599)
    retrieval_outcome: RetrievalOutcome = RetrievalOutcome.unknown
    content_hash: str | None = Field(default=None, max_length=128)
    freshness: Freshness = Freshness.unknown

    _url = field_validator("url")(validate_http_url)
    _utc = field_validator("retrieved_at")(ensure_utc)

    @model_validator(mode="after")
    def _domain_matches_url(self) -> "SourceObservation":
        host = urlsplit(self.url).hostname
        if host is None or host.lower() != self.domain.lower():
            raise ValueError("domain must match the URL host")
        return self