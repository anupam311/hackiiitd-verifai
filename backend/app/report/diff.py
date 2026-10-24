"""Snapshot comparison between two reports of the same opportunity."""
import datetime as dt
from typing import Literal

from pydantic import BaseModel

from app.report.models import ClaimReport, VerificationReport
from app.schemas.enums import ClaimType, OpportunityStatus, VerificationStatus


class ClaimChange(BaseModel):
    claim_type: ClaimType
    change: Literal["changed", "appeared", "disappeared", "became_stale"]
    old_status: VerificationStatus | None
    new_status: VerificationStatus | None
    old_value: str | None
    new_value: str | None
    note: str | None = None


class ReportDiff(BaseModel):
    old_run_id: str
    new_run_id: str
    old_generated_at: dt.datetime
    new_generated_at: dt.datetime
    status_before: OpportunityStatus
    status_after: OpportunityStatus
    changes: list[ClaimChange]
    unchanged: int


def _change(kind: str, old: ClaimReport | None, new: ClaimReport | None, claim_type: ClaimType,
            note: str | None = None) -> ClaimChange:
    return ClaimChange(claim_type=claim_type, change=kind, note=note,
                       old_status=old.status if old else None, new_status=new.status if new else None,
                       old_value=old.normalized_value if old else None,
                       new_value=new.normalized_value if new else None)


def diff_reports(old: VerificationReport, new: VerificationReport) -> ReportDiff:
    a = {c.claim_type: c for c in old.claims}
    b = {c.claim_type: c for c in new.claims}
    changes, unchanged = [], 0
    for t in ClaimType:
        o, n = a.get(t), b.get(t)
        if o is None and n is None:
            continue
        if n is None:
            changes.append(_change("disappeared", o, None, t, "This claim was not evaluated in the newer run."))
        elif o is None:
            changes.append(_change("appeared", None, n, t))
        elif n.stale and not o.stale and o.normalized_value == n.normalized_value:
            # Staleness also lowers the status; report the cause, not just the effect.
            changes.append(_change("became_stale", o, n, t, "Same value, but the evidence is now older than its freshness window."))
        elif o.status != n.status or o.normalized_value != n.normalized_value:
            note = None
            if n.status == VerificationStatus.unavailable:
                note = "Evidence is now unavailable. A source may be inaccessible; that does not mean the information changed."
            changes.append(_change("changed", o, n, t, note))
        else:
            unchanged += 1
    return ReportDiff(old_run_id=old.run_id, new_run_id=new.run_id, old_generated_at=old.generated_at,
                      new_generated_at=new.generated_at, status_before=old.status, status_after=new.status,
                      changes=changes, unchanged=unchanged)