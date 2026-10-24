"""Provider-neutral discovery interface. Real adapters (e.g. TinyFish) implement DiscoveryProvider."""
import datetime as dt
from typing import Protocol

from pydantic import BaseModel, Field

from app.schemas.discovery import DiscoverySearchRequest
from app.schemas.enums import RetrievalOutcome, SourceType


class RawSourceRecord(BaseModel):
    """What a provider returns for one page. Untrusted and un-normalized; see normalize.py."""

    url: str
    title: str | None = None
    retrieved_at: dt.datetime  # set by the provider at fetch time; never invented later
    http_status: int | None = None
    retrieval_outcome: RetrievalOutcome | None = None
    source_type_hint: SourceType | None = None
    content_hash: str | None = None
    # Page text is untrusted and may be large or sensitive: excluded from repr/logs.
    content_text: str | None = Field(default=None, max_length=500_000, repr=False)


class DiscoveryResult(BaseModel):
    records: list[RawSourceRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    complete: bool = True  # False => partial results


class DiscoveryProvider(Protocol):
    name: str

    async def discover(self, request: DiscoverySearchRequest) -> DiscoveryResult: ...