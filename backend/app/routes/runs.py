import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse

from app.runs.manager import Run, RunManager
from app.runs.models import RunStatus

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])
RunId = Annotated[str, Path(min_length=1, max_length=64)]
POLL_S = 0.1
HEARTBEAT_EVERY = 150  # polls (~15 s)


def _get(request: Request, run_id: str) -> tuple[RunManager, Run]:
    mgr: RunManager = request.app.state.runs
    run = mgr.get(run_id)
    if run is None:
        raise HTTPException(404, "Run not found.")
    return mgr, run


@router.get("/{run_id}", response_model=RunStatus)
def get_run(request: Request, run_id: RunId, after: int = Query(0, ge=0)):
    mgr, run = _get(request, run_id)
    return mgr.status(run, after)


@router.post("/{run_id}/cancel", status_code=202, response_model=RunStatus)
def cancel_run(request: Request, run_id: RunId):
    """Idempotent. Stops pending work; results already saved are kept."""
    mgr, run = _get(request, run_id)
    mgr.cancel(run_id)
    return mgr.status(run)


@router.get("/{run_id}/events")
async def run_events(request: Request, run_id: RunId, after: int = Query(0, ge=0),
                     last_event_id: Annotated[int | None, Header()] = None):
    """Server-Sent Events of real pipeline events. Resumable with `after` or the Last-Event-ID header."""
    _, run = _get(request, run_id)

    async def stream():
        seq, idle = last_event_id if last_event_id is not None else after, 0
        while True:
            new = [e for e in run.events if e.seq > seq]
            for e in new:
                seq, idle = e.seq, 0
                yield f"id: {e.seq}\nevent: {e.type}\ndata: {json.dumps(e.model_dump(mode='json'))}\n\n"
            if run.finished and not new:
                return
            if await request.is_disconnected():
                return
            idle += 1
            if idle % HEARTBEAT_EVERY == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_S)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})