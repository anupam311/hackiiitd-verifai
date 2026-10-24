import datetime as dt

from pydantic import BaseModel, Field

from app.schemas.enums import OpportunityCategory, RunState
from app.schemas.opportunity import Opportunity


class DiscoverySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    location: str | None = Field(default=None, max_length=200)
    categories: list[OpportunityCategory] = Field(default_factory=list, max_length=10)
    fields_of_study: list[str] = Field(default_factory=list, max_length=10)
    deadline_before: dt.date | None = None
    limit: int = Field(default=20, ge=1, le=50)


class DiscoverySearchResponse(BaseModel):
    run_id: str
    state: RunState
    opportunities: list[Opportunity] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)