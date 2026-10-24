import asyncio
import datetime as dt
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.ai.errors import LLMAuthError, LLMUnavailable
from app.config import Settings
from app.discovery.base import RawSourceRecord
from app.discovery.errors import ProviderAuthError, ProviderUnavailable
from app.discovery.mock import MockDiscoveryProvider
from app.discovery.retry import RetryPolicy
from app.main import create_app
from app.repositories.memory import InMemoryStore
from app.runs.manager import RunManager, TooManyRuns
from app.runs.models import RunKind
from app.runs.pipeline import PipelineDeps, run_discovery
from app.schemas.discovery import DiscoverySearchRequest
from app.schemas.enums import ClaimType as C, OpportunityStatus, RunState, SourceType as T, VerificationStatus as S

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 6, 1, 12, tzinfo=UTC)
AT = NOW - dt.timedelta(hours=1)
FAST = RetryPolicy(base_delay_s=0)
REQ = DiscoverySearchRequest(query="software internships")

OFFICIAL_TEXT = ("OFFICIAL Example Org Software Internship. Applications are open. "
                 "Deadline: June 15, 2026. Stipend: INR 1,20,000 per month.")
AGG_TEXT = "AGGREGATOR Software Internship at Example Org. Stipend: INR 1,10,000 per month."


def f(t, v, ex, c=0.9):
    return {"claim_type": t, "extracted_value": v, "excerpt": ex, "confidence": c}


PAYLOADS = {
    "OFFICIAL": {"opportunity_title": "Software Internship", "opportunity_category": "internship", "facts": [
        f("organization", "Example Org", "Example Org Software Internship"),
        f("application_status", "open", "Applications are open."),
        f("deadline", "June 15, 2026", "Deadline: June 15, 2026."),
        f("stipend", "INR 1,20,000 per month", "Stipend: INR 1,20,000 per month.")]},
    "AGGREGATOR": {"opportunity_title": "Software Internship", "opportunity_category": "internship", "facts": [
        f("organization", "Example Org", "Example Org"),
        f("stipend", "INR 1,10,000 per month", "Stipend: INR 1,10,000 per month.")]},
}


class ScriptedLLM:
    name, model = "fake", "m"

    def __init__(self, fail=None):
        self.fail = fail or {}

    async def complete_json(self, *, system, user, schema, schema_name):
        for marker, exc in self.fail.items():
            if marker in user:
                raise exc
        for marker, payload in PAYLOADS.items():
            if marker in user:
                return json.dumps(payload)
        raise AssertionError("unexpected page")


def rec(url, text=None, status=200, hint=None):
    return RawSourceRecord(url=url, retrieved_at=AT, http_status=status, content_text=text, source_type_hint=hint)


RECORDS = [rec("https://careers.example.com/apply", OFFICIAL_TEXT, hint=T.official),
           rec("https://internshala.com/x", AGG_TEXT),
           rec("https://old.example.org/gone", None, status=404)]


def deps(provider=None, llm=None, store=None):
    return PipelineDeps(provider=provider or MockDiscoveryProvider(RECORDS), llm=llm or ScriptedLLM(),
                        store=store or InMemoryStore(), retry=FAST, extract_retry=FAST, clock=lambda: NOW)


async def finish(run, timeout=5.0):
    end = time.monotonic() + timeout
    while not run.finished and time.monotonic() < end:
        await asyncio.sleep(0.01)
    assert run.finished


def go(d, mgr=None):
    async def main():
        m = mgr or RunManager(clock=lambda: NOW)
        run = m.start(RunKind.discovery, lambda ctx: run_discovery(ctx, REQ, d))
        await finish(run)
        return m, run
    return asyncio.run(main())


def types(run):
    return [e.type for e in run.events]


def test_full_run_produces_verified_report_and_progress_events():
    store = InMemoryStore()
    m, run = go(deps(store=store))
    assert run.state == RunState.completed and run.error_code is None
    ev = types(run)
    assert ev[0] == "run.started" and ev[-1] == "run.completed"
    for t in ("discovery.started", "discovery.completed", "normalize.completed", "extract.started",
              "extract.completed", "source.unavailable", "opportunity.ready"):
        assert t in ev
    assert [e.seq for e in run.events] == list(range(1, len(ev) + 1))
    assert len(run.opportunities) == 1
    opp = run.opportunities[0]
    assert opp.status == OpportunityStatus.open and opp.title == "Software Internship" and opp.is_demo is False
    assert opp.deadline.is_certain and opp.deadline.date.isoformat() == "2026-06-15"
    report = store.get_latest_report(opp.id)
    assert report.run_id == run.id
    stipend = next(c for c in report.claims if c.claim_type == C.stipend)
    assert stipend.status == S.confirmed and stipend.normalized_value == "INR 120000/month"
    assert {e.domain for e in stipend.evidence} == {"careers.example.com", "internshala.com"}
    assert any("old.example.org could not be retrieved" in w for w in run.warnings)
    assert all("software internships" not in e.message.lower() for e in run.events)  # query not echoed
    st = m.status(run, after=3)
    assert st.elapsed_s == 0 and st.last_seq == len(ev) and st.events[0].seq == 4


def test_transient_provider_errors_are_retried_and_reported():
    p = MockDiscoveryProvider(RECORDS, errors=[ProviderUnavailable(), ProviderUnavailable()])
    _, run = go(deps(provider=p))
    retries = [e for e in run.events if e.type == "discovery.retry"]
    assert [e.data["attempt"] for e in retries] == [1, 2] and retries[0].data["code"] == "PROVIDER_UNAVAILABLE"
    assert run.state == RunState.completed and p.calls == 3


def test_permanent_provider_error_fails_the_run_without_results():
    _, run = go(deps(provider=MockDiscoveryProvider(errors=[ProviderAuthError()])))
    assert run.state == RunState.failed and run.error_code == "PROVIDER_AUTH_ERROR"
    assert types(run)[-1] == "run.failed" and not run.opportunities


def test_one_failed_extraction_gives_partial_results():
    llm = ScriptedLLM(fail={"AGGREGATOR": LLMUnavailable()})
    _, run = go(deps(llm=llm))
    assert run.state == RunState.partial and len(run.opportunities) == 1
    failed = [e for e in run.events if e.type == "extract.failed"]
    assert failed and failed[0].data["domain"] == "internshala.com" and failed[0].data["code"] == "LLM_UNAVAILABLE"
    assert types(run)[-1] == "run.partial"


def test_llm_auth_problem_fails_the_whole_run():
    _, run = go(deps(llm=ScriptedLLM(fail={"OFFICIAL": LLMAuthError(), "AGGREGATOR": LLMAuthError()})))
    assert run.state == RunState.failed and run.error_code == "LLM_AUTH_ERROR"


def test_incomplete_provider_result_is_partial():
    _, run = go(deps(provider=MockDiscoveryProvider(RECORDS, complete=False, warnings=["<b>truncated</b>"])))
    assert run.state == RunState.partial and "truncated" in run.warnings and all("<" not in w for w in run.warnings)


def test_invalid_records_make_run_partial_and_empty_results_warn():
    bad = RawSourceRecord(url="javascript:x", retrieved_at=AT)
    _, run = go(deps(provider=MockDiscoveryProvider([bad])))
    assert run.state == RunState.partial and not run.opportunities
    _, empty = go(deps(provider=MockDiscoveryProvider([])))
    assert empty.state == RunState.completed and "No sources were found." in empty.warnings


def test_cancellation_stops_work_and_emits_cancelled():
    async def main():
        m = RunManager(clock=lambda: NOW)
        d = deps(provider=MockDiscoveryProvider(RECORDS, delay_s=5))
        run = m.start(RunKind.discovery, lambda ctx: run_discovery(ctx, REQ, d))
        await asyncio.sleep(0.05)
        assert m.cancel(run.id) and not m.cancel("nope")
        await finish(run)
        return run
    run = asyncio.run(main())
    assert run.state == RunState.cancelled and types(run)[-1] == "run.cancelled" and not run.opportunities


def test_active_run_cap_and_eviction():
    async def main():
        m = RunManager(max_active=1, max_runs=2, clock=lambda: NOW)
        slow = deps(provider=MockDiscoveryProvider(RECORDS, delay_s=5))
        r1 = m.start(RunKind.discovery, lambda ctx: run_discovery(ctx, REQ, slow))
        with pytest.raises(TooManyRuns):
            m.start(RunKind.discovery, lambda ctx: run_discovery(ctx, REQ, slow))
        m.cancel(r1.id)
        await finish(r1)
        ids = [m.start(RunKind.discovery, lambda ctx: run_discovery(ctx, REQ, deps())).id for _ in range(1)]
        await finish(m.get(ids[0]))
        for _ in range(2):
            r = m.start(RunKind.discovery, lambda ctx: run_discovery(ctx, REQ, deps()))
            await finish(r)
        return m, r1
    m, r1 = asyncio.run(main())
    assert m.get(r1.id) is None  # oldest finished run evicted


# ---- HTTP ----
def api(**kw):
    kw.setdefault("provider", MockDiscoveryProvider(RECORDS))
    kw.setdefault("llm", ScriptedLLM())
    return TestClient(create_app(Settings(), retry_policy=FAST, extract_retry_policy=FAST, **kw))


def wait_done(c, run_id):
    for _ in range(100):
        body = c.get(f"/api/v1/runs/{run_id}").json()
        if body["state"] in ("completed", "partial", "failed", "cancelled"):
            return body
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_search_without_configuration_returns_503_standard_error():
    r = TestClient(create_app(Settings())).post("/api/v1/discovery/search", json={"query": "x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert r.json()["error"]["request_id"].startswith("req_")


def test_search_validates_input():
    with api() as c:
        assert c.post("/api/v1/discovery/search", json={"query": ""}).json()["error"]["code"] == "VALIDATION_ERROR"
        assert c.post("/api/v1/discovery/search", json={"query": "x", "limit": 99}).status_code == 400


def test_search_run_status_and_sse_events():
    with api() as c:
        r = c.post("/api/v1/discovery/search", json={"query": "software internships"})
        assert r.status_code == 202
        start = r.json()
        assert start["state"] in ("queued", "running") and start["opportunities"] == [] and start["run_id"].startswith("run_")
        body = wait_done(c, start["run_id"])
        assert body["state"] == "completed" and len(body["opportunities"]) == 1 and body["events"][-1]["type"] == "run.completed"
        assert c.get(f"/api/v1/opportunities/{body['opportunities'][0]['id']}/report").status_code == 200
        sse = c.get(f"/api/v1/runs/{start['run_id']}/events")
        assert sse.headers["content-type"].startswith("text/event-stream")
        assert "event: run.started" in sse.text and "event: run.completed" in sse.text and "id: 1\n" in sse.text
        resumed = c.get(f"/api/v1/runs/{start['run_id']}/events", headers={"Last-Event-ID": str(body["last_seq"] - 1)})
        assert resumed.text.count("event:") == 1 and "run.completed" in resumed.text
        assert c.get(f"/api/v1/runs/{start['run_id']}?after={body['last_seq']}").json()["events"] == []


def test_run_not_found_and_cancel_endpoint():
    with api() as c:
        for r in (c.get("/api/v1/runs/nope"), c.get("/api/v1/runs/nope/events"), c.post("/api/v1/runs/nope/cancel")):
            assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
        slow = api(provider=MockDiscoveryProvider(RECORDS, delay_s=5))
    with slow as c:
        rid = c.post("/api/v1/discovery/search", json={"query": "x"}).json()["run_id"]
        assert c.post(f"/api/v1/runs/{rid}/cancel").status_code == 202
        assert wait_done(c, rid)["state"] == "cancelled"
        assert c.post(f"/api/v1/runs/{rid}/cancel").status_code == 202  # idempotent


def test_too_many_active_runs_returns_429():
    slow = TestClient(create_app(Settings(), provider=MockDiscoveryProvider(RECORDS, delay_s=5), llm=ScriptedLLM(),
                                 run_manager=RunManager(max_active=1)))
    with slow as c:
        assert c.post("/api/v1/discovery/search", json={"query": "x"}).status_code == 202
        r = c.post("/api/v1/discovery/search", json={"query": "y"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"


def test_cancelling_a_run_before_it_starts_still_finishes_it():
    async def main():
        m = RunManager(clock=lambda: NOW)
        run = m.start(RunKind.discovery, lambda ctx: run_discovery(ctx, REQ, deps()))
        m.cancel(run.id)  # task has not had a chance to run yet
        await finish(run)
        return run
    run = asyncio.run(main())
    assert run.state == RunState.cancelled and types(run)[-1] == "run.cancelled" and run.completed_at