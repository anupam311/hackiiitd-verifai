import datetime as dt
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import RunState
from app.schemas.opportunity import Opportunity


class RunKind(str, Enum):
    discovery = "discovery"
    recheck = "recheck"


class RunEvent(BaseModel):
    seq: int
    type: str
    message: str
    at: dt.datetime
    data: dict[str, Any] = Field(default_factory=dict)  # small, non-sensitive values only


class RunStatus(BaseModel):
    run_id: str
    kind: RunKind
    opportunity_id: str | None = None  # set for rechecks
    state: RunState
    started_at: dt.datetime
    completed_at: dt.datetime | None
    elapsed_s: float
    opportunities: list[Opportunity]  # partial results appear here as they become ready
    warnings: list[str]
    error_code: str | None
    last_seq: int
    events: list[RunEvent]