from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.report.builder import build_comparison
from app.report.models import SourceComparison, VerificationReport
from app.repositories.base import Store
from app.schemas.opportunity import Opportunity

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