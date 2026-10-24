import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.report.builder import build_comparison, build_report
from app.repositories.memory import InMemoryStore
from app.repositories.sqlite import SqliteStore
from app.schemas.enums import (ClaimType as C, OpportunityStatus, RetrievalOutcome, SourceType as T,
                               VerificationStatus as S)
from app.schemas.opportunity import Opportunity
from app.schemas.source import SourceObservation
from app.verification.models import EvidenceItem
from app.verification.policy import verify_opportunity

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 6, 1, 12, tzinfo=UTC)


def obs(domain, stype, hours=1.0, outcome=RetrievalOutcome.ok):
    return SourceObservation(id=f"obs-{domain}", url=f"https://{domain}/p", domain=domain, source_type=stype,
                             retrieved_at=NOW - dt.timedelta(hours=hours), retrieval_outcome=outcome)


def ev(o, claim, value, conf=0.9):
    return EvidenceItem(claim_type=claim, extracted_value=value, excerpt=value, evidence_locator="text:0-5",
                        confidence=conf, observation=o)


OFFICIAL = obs("careers.example.com", T.official)
AGG = obs("jobs.example.net", T.aggregator)
DEAD = obs("old.example.org", T.community, outcome=RetrievalOutcome.not_found)


def make_report(evidence=None, sources=None):
    sources = sources or [AGG, DEAD, OFFICIAL]  # deliberately not in display order
    evidence = evidence if evidence is not None else [
        ev(OFFICIAL, C.stipend, "₹1,20,000 / month"), ev(AGG, C.stipend, "₹1,10,000 / month"),
        ev(OFFICIAL, C.application_status, "Open"), ev(OFFICIAL, C.deadline, "June 15"),
        ev(OFFICIAL, C.duration, "12 weeks"), ev(AGG, C.duration, "12 weeks"),
    ]
    return build_report("opp1", "run1", verify_opportunity(evidence, sources, NOW), sources, NOW)


def test_report_joins_evidence_orders_sources_and_derives_status():
    r = make_report()
    assert [s.domain for s in r.sources] == ["careers.example.com", "jobs.example.net", "old.example.org"]
    assert r.status == OpportunityStatus.open
    stip = next(c for c in r.claims if c.claim_type == C.stipend)
    assert stip.status == S.confirmed and {e.domain for e in stip.evidence} == {"careers.example.com", "jobs.example.net"}
    assert all(e.url.startswith("https://") and e.retrieved_at and e.evidence_locator for e in stip.evidence)
    assert r.summary.total == len(r.claims) and "probability" in r.summary.formula


def test_report_rejects_evidence_for_unknown_source():
    with pytest.raises(ValueError):
        build_report("o", "r", verify_opportunity([ev(OFFICIAL, C.deadline, "2026-06-15")], [], NOW), [], NOW)


def test_comparison_rows_cells_and_conflict_callout():
    cmp = build_comparison(make_report())
    assert [s.domain for s in cmp.sources][0] == "careers.example.com" and cmp.sources[0].is_authoritative
    rows = {r.claim_type: r for r in cmp.rows}
    stip = rows[C.stipend]
    assert stip.agreement == "conflict"
    assert [c.state for c in stip.cells] == ["agrees", "differs", "unavailable"]
    assert rows[C.duration].agreement == "agree"
    assert rows[C.deadline].agreement == "partial"  # official page gives no year
    assert rows[C.application_url].agreement == "missing"
    callout = next(c for c in cmp.conflicts if c.claim_type == C.stipend)
    assert {v.domain for v in callout.values} == {"careers.example.com", "jobs.example.net"}
    assert "authoritative" in callout.message and all(v.url for v in callout.values)


def test_conflict_between_official_sources_is_flagged_as_conflicting():
    other = obs("jobs.example.com", T.employer)
    r = make_report([ev(OFFICIAL, C.deadline, "June 15, 2026"), ev(other, C.deadline, "June 20, 2026")],
                    [OFFICIAL, other])
    cmp = build_comparison(r)
    assert cmp.conflicts[0].status == S.conflicting and "disagree" in cmp.conflicts[0].message


def test_warnings_cover_stale_evidence_and_failed_sources_without_claiming_closed():
    old = obs("careers.example.com", T.official, hours=24 * 5)  # application_status window is 2 days
    r = make_report([ev(old, C.application_status, "Open")], [old, DEAD])
    w = " ".join(build_comparison(r).warnings)
    assert "stale" in w and "old.example.org could not be retrieved" in w and "does not show the opportunity is closed" in w
    assert r.status == OpportunityStatus.unknown


# ---- HTTP ----
def client(store=None):
    return TestClient(create_app(Settings(), store=store or InMemoryStore()))


def seeded():
    store = SqliteStore(":memory:")
    store.save_opportunity(Opportunity(id="opp1", title="Test role", organization="Example Org",
                                       category="internship", canonical_url="https://careers.example.com/p", is_demo=True))
    store.save_report(make_report())
    return store


def assert_404(resp):
    assert resp.status_code == 404
    err = resp.json()["error"]
    assert err["code"] == "NOT_FOUND" and err["request_id"].startswith("req_")


def test_endpoints_return_documented_data():
    c = client(seeded())
    assert c.get("/api/v1/opportunities/opp1").json()["is_demo"] is True
    rep = c.get("/api/v1/opportunities/opp1/report").json()
    assert rep["run_id"] == "run1" and rep["claims"] and rep["sources"][0]["source_type"] == "official"
    src = c.get("/api/v1/opportunities/opp1/sources").json()
    assert src["conflicts"] and src["rows"] and src["sources"]


def test_missing_resources_use_standard_error_shape():
    c = client(seeded())
    for path in ("/api/v1/opportunities/nope", "/api/v1/opportunities/nope/report", "/api/v1/opportunities/nope/sources"):
        assert_404(c.get(path))
    empty = InMemoryStore()
    empty.save_opportunity(seeded().get_opportunity("opp1"))
    r = client(empty).get("/api/v1/opportunities/opp1/report")
    assert_404(r) and "No verification report" in r.json()["error"]["message"]


def test_overlong_id_is_a_validation_error():
    r = client().get("/api/v1/opportunities/" + "x" * 65)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"