"""In-process run registry. Runs are asyncio tasks; events are real pipeline events, never simulated.

Policies: at most `max_active` unfinished runs (else TooManyRuns -> HTTP 429); cancelling stops pending
work but keeps results already saved; finished runs are evicted oldest-first beyond `max_runs`.
"""
import asyncio
import datetime as dt
import logging
import uuid
from typing import Any, Awaitable, Callable

from app.ai.errors import LLMError
from app.discovery.errors import ProviderError
from app.runs.models import RunEvent, RunKind, RunStatus
from app.schemas.common import utc_now
from app.schemas.enums import RunState
from app.schemas.opportunity import Opportunity

logger = logging.getLogger("verifai.runs")
FINISHED = {RunState.completed, RunState.partial, RunState.failed, RunState.cancelled}
Work = Callable[["RunContext"], Awaitable[RunState]]


class TooManyRuns(Exception):
    pass


class Run:
    def __init__(self, kind: RunKind, now: dt.datetime):
        self.id = f"run_{uuid.uuid4().hex[:16]}"
        self.kind = kind
        self.state = RunState.queued
        self.started_at = now
        self.completed_at: dt.datetime | None = None
        self.events: list[RunEvent] = []
        self.opportunities: list[Opportunity] = []
        self.warnings: list[str] = []
        self.error_code: str | None = None
        self.task: asyncio.Task | None = None

    @property
    def finished(self) -> bool:
        return self.state in FINISHED


class RunContext:
    def __init__(self, run: Run, clock: Callable[[], dt.datetime]):
        self._run, self._clock = run, clock

    @property
    def run_id(self) -> str:
        return self._run.id

    def emit(self, type: str, message: str, **data: Any) -> None:
        self._run.events.append(RunEvent(seq=len(self._run.events) + 1, type=type, message=message,
                                         at=self._clock(), data=data))

    def warn(self, message: str) -> None:
        self._run.warnings.append(message[:300])

    def add_opportunity(self, opportunity: Opportunity) -> None:
        self._run.opportunities.append(opportunity)


class RunManager:
    def __init__(self, *, max_active: int = 5, max_runs: int = 200,
                 clock: Callable[[], dt.datetime] = utc_now):
        self.max_active, self.max_runs, self.clock = max_active, max_runs, clock
        self._runs: dict[str, Run] = {}

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def start(self, kind: RunKind, work: Work) -> Run:
        if sum(1 for r in self._runs.values() if not r.finished) >= self.max_active:
            raise TooManyRuns()
        run = Run(kind, self.clock())
        self._runs[run.id] = run
        run.task = asyncio.get_running_loop().create_task(self._execute(run, work))
        run.task.add_done_callback(lambda _t, r=run: self._on_task_done(r))
        return run

    def cancel(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        if run.task and not run.finished:
            run.task.cancel()
        return True

    async def shutdown(self) -> None:
        tasks = [r.task for r in self._runs.values() if r.task and not r.finished]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute(self, run: Run, work: Work) -> None:
        ctx = RunContext(run, self.clock)
        run.state = RunState.running
        ctx.emit("run.started", "Run started.")
        final, message = RunState.failed, "Run failed."
        try:
            final = await work(ctx)
            message = {RunState.completed: "Run completed.",
                       RunState.partial: "Run finished with partial results."}.get(final, "Run finished.")
        except asyncio.CancelledError:
            final, message = RunState.cancelled, "Run cancelled. Results saved so far are kept."
        except (ProviderError, LLMError) as exc:
            run.error_code, message = exc.code, f"Run failed ({exc.code})."
        except Exception as exc:  # noqa: BLE001
            logger.error("run %s crashed type=%s", run.id, type(exc).__name__)  # no details/content
            run.error_code, message = "INTERNAL_ERROR", "Run failed unexpectedly."
        self._finalize(run, final, message)

    def _finalize(self, run: Run, final: RunState, message: str) -> None:
        RunContext(run, self.clock).emit(
            f"run.{final.value}", message, **({"error_code": run.error_code} if run.error_code else {}))
        run.completed_at = self.clock()
        run.state = final  # set last: stream consumers end only after the final event exists
        self._evict()

    def _on_task_done(self, run: Run) -> None:
        # Covers a task cancelled before it ever started (its handler never ran).
        if not run.finished:
            self._finalize(run, RunState.cancelled, "Run cancelled. Results saved so far are kept.")

    def _evict(self) -> None:
        while len(self._runs) > self.max_runs:
            oldest = next((k for k, r in self._runs.items() if r.finished), None)
            if oldest is None:
                break
            del self._runs[oldest]

    def status(self, run: Run, after: int = 0) -> RunStatus:
        end = run.completed_at or self.clock()
        return RunStatus(
            run_id=run.id, kind=run.kind, state=run.state, started_at=run.started_at,
            completed_at=run.completed_at, elapsed_s=round((end - run.started_at).total_seconds(), 3),
            opportunities=list(run.opportunities), warnings=list(run.warnings), error_code=run.error_code,
            last_seq=len(run.events), events=[e for e in run.events if e.seq > after])