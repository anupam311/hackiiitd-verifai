import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel

from app.auth.deps import current_user_id
from app.report.builder import build_comparison
from app.report.diff import ReportDiff, diff_reports
from app.report.models import SourceComparison, VerificationReport
from app.repositories.base import Store
from app.runs.manager import TooManyRuns
from app.runs.models import RunKind
from app.runs.pipeline import PipelineDeps, run_recheck
from app.schemas.enums import OpportunityCategory, OpportunityStatus, RunState
from app.schemas.opportunity import Opportunity
from app.verification.models import VerificationSummary

router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunities"])
OppId = Annotated[str, Path(min_length=1, max_length=64)]


def get_store(request: Request) -> Store:
    return request.app.state.store


def _report(store: Store, opportunity_id: str) -> VerificationReport:
    if store.get_opportunity(opportunity_id) is None:
        raise HTTPException(404, "Opportunity not found.")
    report = store.get_latest_report(opportunity_id)
    if report is None:
        raise HTTPException(404, "No verification report exists for this opportunity yet.")
    return report


@router.get("/{opportunity_id}", response_model=Opportunity)
def get_opportunity(opportunity_id: OppId, store: Store = Depends(get_store)):
    opp = store.get_opportunity(opportunity_id)
    if opp is None:
        raise HTTPException(404, "Opportunity not found.")
    return opp


@router.get("/{opportunity_id}/report", response_model=VerificationReport)
def get_report(opportunity_id: OppId, store: Store = Depends(get_store)):
    return _report(store, opportunity_id)


@router.get("/{opportunity_id}/sources", response_model=SourceComparison)
def get_sources(opportunity_id: OppId, store: Store = Depends(get_store)):
    return build_comparison(_report(store, opportunity_id))


class OpportunityPage(BaseModel):
    items: list[Opportunity]
    limit: int
    offset: int


class HistoryEntry(BaseModel):
    run_id: str
    generated_at: dt.datetime
    status: OpportunityStatus
    summary: VerificationSummary
    changes_since_previous: ReportDiff | None  # None for the oldest snapshot


class HistoryResponse(BaseModel):
    opportunity_id: str
    runs: list[HistoryEntry]  # newest first


class RecheckResponse(BaseModel):
    run_id: str
    state: RunState


@router.get("", response_model=OpportunityPage)
def list_opportunities(q: Annotated[str | None, Query(max_length=200)] = None,
                       category: OpportunityCategory | None = None,
                       limit: Annotated[int, Query(ge=1, le=50)] = 20,
                       offset: Annotated[int, Query(ge=0)] = 0, store: Store = Depends(get_store)):
    items = store.list_opportunities(q=q, category=category.value if category else None, limit=limit, offset=offset)
    return OpportunityPage(items=items, limit=limit, offset=offset)


@router.get("/{opportunity_id}/history", response_model=HistoryResponse)
def get_history(opportunity_id: OppId, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                store: Store = Depends(get_store)):
    if store.get_opportunity(opportunity_id) is None:
        raise HTTPException(404, "Opportunity not found.")
    reports = store.list_reports(opportunity_id, limit + 1)  # +1 so the oldest shown has a predecessor
    entries = []
    for i, r in enumerate(reports[:limit]):
        prev = reports[i + 1] if i + 1 < len(reports) else None
        entries.append(HistoryEntry(run_id=r.run_id, generated_at=r.generated_at, status=r.status,
                                    summary=r.summary, changes_since_previous=diff_reports(prev, r) if prev else None))
    return HistoryResponse(opportunity_id=opportunity_id, runs=entries)


@router.post("/{opportunity_id}/recheck", status_code=202, response_model=RecheckResponse)
async def recheck(opportunity_id: OppId, request: Request, _user: str = Depends(current_user_id)):
    st = request.app.state
    if st.store.get_opportunity(opportunity_id) is None:
        raise HTTPException(404, "Opportunity not found.")
    if st.store.get_latest_report(opportunity_id) is None:
        raise HTTPException(404, "No previous verification report exists, so there are no sources to recheck.")
    if st.provider is None or st.llm is None:
        raise HTTPException(503, "Rechecking is not configured on this server "
                                 "(discovery provider or LLM credentials are missing).")
    if st.runs.active_for(opportunity_id):
        raise HTTPException(409, "A recheck for this opportunity is already running.")
    deps = PipelineDeps(provider=st.provider, llm=st.llm, store=st.store, retry=st.retry_policy,
                        extract_retry=st.extract_retry_policy)
    try:
        run = st.runs.start(RunKind.recheck, lambda ctx: run_recheck(ctx, opportunity_id, deps),
                            opportunity_id=opportunity_id)
    except TooManyRuns:
        raise HTTPException(429, "Too many runs are active. Try again shortly.") from None
    return RecheckResponse(run_id=run.id, state=run.state)