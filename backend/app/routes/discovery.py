from fastapi import APIRouter, HTTPException, Request

from app.runs.manager import TooManyRuns
from app.runs.models import RunKind
from app.runs.pipeline import PipelineDeps, run_discovery
from app.schemas.discovery import DiscoverySearchRequest, DiscoverySearchResponse

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


@router.post("/search", status_code=202, response_model=DiscoverySearchResponse)
async def search(body: DiscoverySearchRequest, request: Request) -> DiscoverySearchResponse:
    """Starts a run and returns immediately. Follow progress via /api/v1/runs/{run_id}[/events]."""
    st = request.app.state
    if st.provider is None or st.llm is None:
        raise HTTPException(503, "Discovery is not configured on this server "
                                 "(discovery provider or LLM credentials are missing).")
    deps = PipelineDeps(provider=st.provider, llm=st.llm, store=st.store, retry=st.retry_policy,
                        extract_retry=st.extract_retry_policy)
    try:
        run = st.runs.start(RunKind.discovery, lambda ctx: run_discovery(ctx, body, deps))
    except TooManyRuns:
        raise HTTPException(429, "Too many runs are active. Try again shortly.") from None
    return DiscoverySearchResponse(run_id=run.id, state=run.state)