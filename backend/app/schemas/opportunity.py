import datetime as dt

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ensure_utc, utc_now, validate_http_url
from app.schemas.enums import OpportunityCategory, OpportunityStatus


class DeadlineInfo(BaseModel):
    """Deadline as found. Original text is always kept; a date is only set when it is unambiguous."""

    raw_text: str = Field(min_length=1, max_length=200)
    date: dt.date | None = None
    timezone_name: str | None = Field(default=None, max_length=64)
    is_certain: bool = False

    @model_validator(mode="after")
    def _certain_requires_date(self) -> "DeadlineInfo":
        if self.is_certain and self.date is None:
            raise ValueError("a certain deadline requires a parsed date")
        return self


class Opportunity(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(min_length=1, max_length=200)
    category: OpportunityCategory
    location: str | None = Field(default=None, max_length=200)
    canonical_url: str
    deadline: DeadlineInfo | None = None
    # Derived from verified claims later; never assumed from a failed fetch or a past deadline.
    status: OpportunityStatus = OpportunityStatus.unknown
    is_demo: bool = False  # demo/seed data must be labeled
    created_at: dt.datetime = Field(default_factory=utc_now)
    updated_at: dt.datetime = Field(default_factory=utc_now)

    _url = field_validator("canonical_url")(validate_http_url)
    _utc = field_validator("created_at", "updated_at")(ensure_utc)