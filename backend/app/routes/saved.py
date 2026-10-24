import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel

from app.auth.deps import current_user_id
from app.repositories.base import Store
from app.routes.opportunities import get_store
from app.schemas.common import utc_now
from app.schemas.enums import OpportunityStatus
from app.schemas.opportunity import Opportunity
from app.verification.models import VerificationSummary

router = APIRouter(prefix="/api/v1/saved", tags=["saved"])
OppId = Annotated[str, Path(min_length=1, max_length=64)]


class SavedItem(BaseModel):
    opportunity: Opportunity
    saved_at: dt.datetime
    latest_status: OpportunityStatus | None  # from the latest report; None if never verified
    latest_summary: VerificationSummary | None
    latest_report_at: dt.datetime | None


def _item(store: Store, opp: Opportunity, saved_at: dt.datetime) -> SavedItem:
    r = store.get_latest_report(opp.id)
    return SavedItem(opportunity=opp, saved_at=saved_at, latest_status=r.status if r else None,
                     latest_summary=r.summary if r else None, latest_report_at=r.generated_at if r else None)


@router.get("", response_model=list[SavedItem])
def list_saved(user_id: str = Depends(current_user_id), store: Store = Depends(get_store)):
    return [_item(store, o, t) for o, t in store.list_saved(user_id)]


@router.put("/{opportunity_id}", response_model=SavedItem)
def save(opportunity_id: OppId, user_id: str = Depends(current_user_id), store: Store = Depends(get_store)):
    opp = store.get_opportunity(opportunity_id)
    if opp is None:
        raise HTTPException(404, "Opportunity not found.")
    return _item(store, opp, store.set_saved(user_id, opportunity_id, utc_now()))


@router.delete("/{opportunity_id}", status_code=204)
def unsave(opportunity_id: OppId, user_id: str = Depends(current_user_id), store: Store = Depends(get_store)):
    if store.get_opportunity(opportunity_id) is None:
        raise HTTPException(404, "Opportunity not found.")
    store.unset_saved(user_id, opportunity_id)
    return Response(status_code=204)