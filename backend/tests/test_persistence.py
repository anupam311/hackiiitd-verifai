import datetime as dt
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import current_user_id
from app.config import Settings
from app.discovery.base import RawSourceRecord
from app.discovery.mock import MockDiscoveryProvider
from app.main import create_app
from app.report.builder import build_report
from app.report.diff import diff_reports
from app.repositories.sqlite import SqliteStore, sqlite_path
from app.schemas.enums import (ClaimType as C, OpportunityStatus, RetrievalOutcome, SourceType as T,
                               VerificationStatus as S)
from app.schemas.opportunity import Opportunity
from app.schemas.source import SourceObservation
from app.verification.models import EvidenceItem
from app.verification.policy import verify_opportunity
from test_runs import FAST, NOW, RECORDS, ScriptedLLM, deps, go, rec, wait_done  # B9 fixtures

UTC = dt.timezone.utc


def opp(id="o1", title="Alpha Role", org="Beta Org", category="internship", at=NOW):
    return Opportunity(id=id, title=title, organization=org, category=category, canonical_url="https://example.com/a",
                       is_demo=True, created_at=at, updated_at=at)


def obs(hours=1.0, domain="careers.example.com", stype=T.official, at=NOW):
    return SourceObservation(id=f"obs-{domain}-{hours}", url=f"https://{domain}/p", domain=domain, source_type=stype,
                             retrieved_at=at - dt.timedelta(hours=hours), retrieval_outcome=RetrievalOutcome.ok)


def ev(o, claim, value):
    return EvidenceItem(claim_type=claim, extracted_value=value, excerpt=value, evidence_locator="text:0-5",
                        confidence=0.9, observation=o)


def rep(run, at, items, hours=1.0, opp_id="o1"):
    o = obs(hours, at=at)
    evidence = [ev(o, c, v) for c, v in items]
    return build_report(opp_id, run, verify_opportunity(evidence, [o], at), [o], at)


# ---- store ----
def test_roundtrip_upsert_and_ordering():
    s = SqliteStore(":memory:")
    s.save_opportunity(opp())
    s.save_opportunity(opp(title="Alpha Role v2"))
    assert s.get_opportunity("o1").title == "Alpha Role v2" and s.get_opportunity("zzz") is None
    t1, t2 = NOW, NOW + dt.timedelta(days=1)
    s.save_report(rep("r1", t1, [(C.location, "Pune")]))
    s.save_report(rep("r2", t2, [(C.location, "Pune")]))
    assert [r.run_id for r in s.list_reports("o1")] == ["r2", "r1"] and s.get_latest_report("o1").run_id == "r2"
    assert s.get_latest_report("zzz") is None


def test_report_requires_existing_opportunity_and_unique_run():
    s = SqliteStore(":memory:")
    with pytest.raises(sqlite3.IntegrityError):
        s.save_report(rep("r1", NOW, []))
    s.save_opportunity(opp())
    s.save_report(rep("r1", NOW, []))
    with pytest.raises(sqlite3.IntegrityError):
        s.save_report(rep("r1", NOW, []))


def test_saved_is_idempotent_and_per_user():
    s = SqliteStore(":memory:")
    s.save_opportunity(opp())
    first = s.set_saved("a", "o1", NOW)
    assert s.set_saved("a", "o1", NOW + dt.timedelta(days=1)) == first  # keeps original saved_at
    assert [o.id for o, _ in s.list_saved("a")] == ["o1"] and s.list_saved("b") == []
    s.unset_saved("a", "o1")
    s.unset_saved("a", "o1")  # idempotent
    assert s.list_saved("a") == []


def test_search_escapes_wildcards_and_filters():
    s = SqliteStore(":memory:")
    s.save_opportunity(opp("o1", "100% Remote", "Acme"))
    s.save_opportunity(opp("o2", "Other", "Acme", "scholarship"))
    assert [o.id for o in s.list_opportunities(q="100%")] == ["o1"]
    assert s.list_opportunities(q="%") != s.list_opportunities()  # '%' is literal, not a wildcard
    assert [o.id for o in s.list_opportunities(category="scholarship")] == ["o2"]
    assert len(s.list_opportunities(limit=1)) == 1 and len(s.list_opportunities(offset=5)) == 0
    assert [o.id for o in s.list_opportunities(q="x' OR '1'='1")] == []


def test_data_survives_reopen(tmp_path):
    path = str(tmp_path / "v.db")
    s = SqliteStore(path)
    s.save_opportunity(opp())
    s.save_report(rep("r1", NOW, [(C.location, "Pune")]))
    s.set_saved("a", "o1", NOW)
    s.close()
    s2 = SqliteStore(path)
    assert s2.get_latest_report("o1").claims and s2.list_saved("a")


def test_sqlite_path():
    assert sqlite_path("sqlite:///./verifai.db") == "./verifai.db"
    assert sqlite_path("sqlite:///:memory:") == ":memory:"
    assert sqlite_path("sqlite:////var/data/v.db") == "/var/data/v.db"
    for bad in ("postgres://x", "sqlite:///"):
        with pytest.raises(ValueError):
            sqlite_path(bad)


# ---- diff ----
def test_diff_reports_changed_appeared_disappeared_unchanged():
    t1, t2 = NOW, NOW + dt.timedelta(days=1)
    old = rep("r1", t1, [(C.stipend, "INR 1,20,000 per month"), (C.application_status, "Open"),
                         (C.duration, "12 weeks"), (C.deadline, "June 15, 2026")])
    new = rep("r2", t2, [(C.stipend, "INR 1,30,000 per month"), (C.application_status, "Applications closed"),
                         (C.location, "Pune"), (C.deadline, "June 15, 2026")])
    d = diff_reports(old, new)
    by = {c.claim_type: c for c in d.changes}
    assert by[C.stipend].change == "changed" and (by[C.stipend].old_value, by[C.stipend].new_value) == ("INR 120000/month", "INR 130000/month")
    assert by[C.application_status].new_value == "closed"
    assert by[C.duration].change == "disappeared" and by[C.location].change == "appeared"
    assert C.deadline not in by and d.unchanged >= 3  # deadline, eligibility, application_url
    assert (d.status_before, d.status_after) == (OpportunityStatus.open, OpportunityStatus.closed)


def test_diff_flags_stale_and_unavailable_without_claiming_the_info_changed():
    t1, t2 = NOW, NOW + dt.timedelta(days=10)
    fresh = rep("r1", t1, [(C.deadline, "June 15, 2026")])
    stale = rep("r2", t2, [(C.deadline, "June 15, 2026")], hours=24 * 9)  # older than the 7-day window
    assert [c.change for c in diff_reports(fresh, stale).changes] == ["became_stale"]
    gone = rep("r3", t2, [])
    ch = next(c for c in diff_reports(fresh, gone).changes if c.claim_type == C.deadline)
    assert ch.change == "changed" and ch.new_status == S.unavailable and "does not mean the information changed" in ch.note


# ---- HTTP ----
def client(store, user="user-a", **kw):
    app = create_app(Settings(), store=store, retry_policy=FAST, extract_retry_policy=FAST, **kw)
    if user:
        app.dependency_overrides[current_user_id] = lambda: user
    return TestClient(app)


def seeded():
    store = SqliteStore(":memory:")
    _, run = go(deps(store=store))
    return store, run.opportunities[0].id


def test_auth_boundary_returns_401_standard_error():
    store, oid = seeded()
    with client(store, user=None) as c:
        for r in (c.get("/api/v1/saved"), c.put(f"/api/v1/saved/{oid}"), c.delete(f"/api/v1/saved/{oid}"),
                  c.post(f"/api/v1/opportunities/{oid}/recheck")):
            assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
            assert r.json()["error"]["request_id"].startswith("req_")
        assert c.get(f"/api/v1/opportunities/{oid}/history").status_code == 200  # public read


def test_saved_flow_with_latest_verification_state_and_user_isolation():
    store, oid = seeded()
    with client(store, "user-a") as a:
        item = a.put(f"/api/v1/saved/{oid}").json()
        assert item["latest_status"] == "open" and item["latest_summary"]["total"] >= 4 and item["opportunity"]["id"] == oid
        assert a.put(f"/api/v1/saved/{oid}").json()["saved_at"] == item["saved_at"]
        assert [x["opportunity"]["id"] for x in a.get("/api/v1/saved").json()] == [oid]
    with client(store, "user-b") as b:
        assert b.get("/api/v1/saved").json() == []
    with client(store, "user-a") as a:
        assert a.delete(f"/api/v1/saved/{oid}").status_code == 204 and a.delete(f"/api/v1/saved/{oid}").status_code == 204
        assert a.get("/api/v1/saved").json() == []
        assert a.put("/api/v1/saved/nope").status_code == 404 and a.delete("/api/v1/saved/nope").status_code == 404


def test_list_opportunities_filters_and_validation():
    store, oid = seeded()
    with client(store) as c:
        assert [o["id"] for o in c.get("/api/v1/opportunities?q=software").json()["items"]] == [oid]
        assert c.get("/api/v1/opportunities?category=scholarship").json()["items"] == []
        assert c.get("/api/v1/opportunities?limit=0").status_code == 400
        assert c.get("/api/v1/opportunities?category=bogus").json()["error"]["code"] == "VALIDATION_ERROR"


def test_recheck_preconditions():
    store, oid = seeded()
    orphan = SqliteStore(":memory:")
    orphan.save_opportunity(opp())
    with client(store, provider=MockDiscoveryProvider(RECORDS), llm=ScriptedLLM()) as c:
        assert c.post("/api/v1/opportunities/nope/recheck").status_code == 404
    with client(orphan, provider=MockDiscoveryProvider(RECORDS), llm=ScriptedLLM()) as c:
        r = c.post("/api/v1/opportunities/o1/recheck")
        assert r.status_code == 404 and "No previous verification report" in r.json()["error"]["message"]
    with client(store) as c:  # no provider/LLM configured
        assert c.post(f"/api/v1/opportunities/{oid}/recheck").status_code == 503


NEW_TEXT = ("OFFICIAL Example Org Software Internship. Applications are closed. "
            "Deadline: June 15, 2026. Stipend: INR 1,30,000 per month.")


class RecheckLLM:
    name, model = "fake", "m"

    async def complete_json(self, *, system, user, schema, schema_name):
        assert "OFFICIAL" in user
        f = lambda t, v, ex: {"claim_type": t, "extracted_value": v, "excerpt": ex, "confidence": 0.9}  # noqa: E731
        return json.dumps({"opportunity_title": "Software Internship", "opportunity_category": "internship", "facts": [
            f("organization", "Example Org", "Example Org Software Internship"),
            f("application_status", "closed", "Applications are closed."),
            f("deadline", "June 15, 2026", "Deadline: June 15, 2026."),
            f("stipend", "INR 1,30,000 per month", "Stipend: INR 1,30,000 per month.")]})


def test_recheck_creates_new_snapshot_and_history_shows_changes():
    store, oid = seeded()
    old_run = store.get_latest_report(oid).run_id
    t = dt.datetime.now(UTC) - dt.timedelta(minutes=1)
    new_records = [RawSourceRecord(url="https://careers.example.com/apply", retrieved_at=t, http_status=200,
                                   content_text=NEW_TEXT, source_type_hint=T.official),
                   RawSourceRecord(url="https://internshala.com/x", retrieved_at=t, http_status=404)]
    provider = MockDiscoveryProvider(new_records)
    with client(store, provider=provider, llm=RecheckLLM()) as c:
        started = c.post(f"/api/v1/opportunities/{oid}/recheck")
        assert started.status_code == 202
        body = wait_done(c, started.json()["run_id"])
        assert body["kind"] == "recheck" and body["opportunity_id"] == oid and body["state"] == "completed"
        types = [e["type"] for e in body["events"]]
        assert types[:2] == ["run.started", "recheck.started"] and "recheck.diff" in types and types[-1] == "run.completed"
        diff_event = next(e for e in body["events"] if e["type"] == "recheck.diff")
        assert diff_event["data"]["changed"] >= 2
        assert any("internshala.com could not be retrieved" in w for w in body["warnings"])
        assert provider.fetch_calls == 1 and provider.calls == 0

        hist = c.get(f"/api/v1/opportunities/{oid}/history").json()
        assert len(hist["runs"]) == 2 and hist["runs"][1]["run_id"] == old_run
        assert hist["runs"][1]["changes_since_previous"] is None  # oldest snapshot
        changes = {x["claim_type"]: x for x in hist["runs"][0]["changes_since_previous"]["changes"]}
        assert changes["application_status"]["old_value"] == "open" and changes["application_status"]["new_value"] == "closed"
        assert changes["stipend"]["old_value"] == "INR 120000/month" and changes["stipend"]["new_value"] == "INR 130000/month"
        assert hist["runs"][0]["status"] == "closed"
        # old snapshot is untouched; the opportunity reflects the new report
        assert store.list_reports(oid)[1].run_id == old_run
        assert c.get(f"/api/v1/opportunities/{oid}").json()["status"] == "closed"
        report = c.get(f"/api/v1/opportunities/{oid}/report").json()
        assert {s["retrieval_outcome"] for s in report["sources"]} == {"ok", "not_found"}


def test_concurrent_recheck_of_same_opportunity_is_a_409():
    store, oid = seeded()
    slow = MockDiscoveryProvider(RECORDS, delay_s=5)
    with client(store, provider=slow, llm=ScriptedLLM()) as c:
        rid = c.post(f"/api/v1/opportunities/{oid}/recheck").json()["run_id"]
        r = c.post(f"/api/v1/opportunities/{oid}/recheck")
        assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"
        c.post(f"/api/v1/runs/{rid}/cancel")
        assert wait_done(c, rid)["state"] == "cancelled"
        assert len(store.list_reports(oid)) == 1  # a cancelled recheck leaves history untouched