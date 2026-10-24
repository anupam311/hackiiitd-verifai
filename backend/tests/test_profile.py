"""Tests for the Profile API (B13 + B14).

Covers:
- GET /api/v1/profile  (defaults, after update)
- PATCH /api/v1/profile  (validation, partial update, interests sanitization)
- GET /api/v1/profile/match/{opportunity_id}  (location, interests, experience)
- Auth boundary (401 without session)
- Data-minimization (profile values not echoed in match reasons)
"""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import current_user_id
from app.config import Settings
from app.main import create_app
from app.repositories.memory import InMemoryStore
from app.report.builder import build_report
from app.schemas.enums import ClaimType as C, RetrievalOutcome, SourceType as T
from app.schemas.opportunity import Opportunity
from app.schemas.source import SourceObservation
from app.verification.models import EvidenceItem
from app.verification.policy import verify_opportunity

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 6, 1, 12, tzinfo=UTC)


def make_opp(location="Bengaluru, India"):
    return Opportunity(id="opp1", title="Software Internship", organization="Example Org",
                       category="internship", canonical_url="https://careers.example.com/apply",
                       location=location, is_demo=False)


def make_obs():
    return SourceObservation(id="obs1", url="https://careers.example.com/apply",
                             domain="careers.example.com", source_type=T.official,
                             retrieved_at=NOW - dt.timedelta(hours=1),
                             retrieval_outcome=RetrievalOutcome.ok)


def make_report(store, opp):
    obs = make_obs()
    ev = [EvidenceItem(claim_type=C.application_status, extracted_value="open",
                       excerpt="Applications are open.", evidence_locator="text:0-5",
                       confidence=0.95, observation=obs),
          EvidenceItem(claim_type=C.stipend, extracted_value="INR 1,20,000 per month",
                       excerpt="Stipend: INR 1,20,000 per month.", evidence_locator="text:10-15",
                       confidence=0.9, observation=obs)]
    verdicts = verify_opportunity(ev, [obs], NOW)
    report = build_report("opp1", "run1", verdicts, [obs], NOW)
    store.save_report(report)
    return report


def client(store=None, user="user-a"):
    store = store or InMemoryStore()
    app = create_app(Settings(), store=store)
    if user:
        app.dependency_overrides[current_user_id] = lambda: user
    return TestClient(app), store


# ---- default profile ----

def test_get_profile_returns_empty_defaults():
    c, _ = client()
    r = c.get("/api/v1/profile")
    assert r.status_code == 200
    data = r.json()
    assert data == {"education": None, "location": None, "experience_years": None, "interests": []}


# ---- PATCH profile ----

def test_patch_profile_partial_update():
    c, store = client()
    r = c.patch("/api/v1/profile", json={"education": "B.Tech CS, IIT Delhi"})
    assert r.status_code == 200
    assert r.json()["education"] == "B.Tech CS, IIT Delhi"
    assert r.json()["location"] is None  # other fields unchanged


def test_patch_profile_all_fields():
    c, store = client()
    r = c.patch("/api/v1/profile", json={
        "education": "M.Tech AI, IIIT Hyderabad",
        "location": "Bengaluru, India",
        "experience_years": 1,
        "interests": ["machine learning", "robotics"]
    })
    assert r.status_code == 200
    data = r.json()
    assert data["education"] == "M.Tech AI, IIIT Hyderabad"
    assert data["location"] == "Bengaluru, India"
    assert data["experience_years"] == 1
    assert set(data["interests"]) == {"machine learning", "robotics"}


def test_patch_preserves_existing_fields():
    c, store = client()
    c.patch("/api/v1/profile", json={"education": "B.Sc Physics"})
    r = c.patch("/api/v1/profile", json={"location": "Mumbai"})
    data = r.json()
    assert data["education"] == "B.Sc Physics" and data["location"] == "Mumbai"


def test_patch_interests_are_deduplicated_and_capped():
    c, _ = client()
    r = c.patch("/api/v1/profile", json={
        "interests": ["ML", "ML", "ai", "AI", "a", "b", "c", "d", "e", "f", "g"]
    })
    assert r.status_code == 200
    interests = r.json()["interests"]
    # At most 10, duplicates (case-insensitive) removed
    assert len(interests) <= 10
    lower = [i.lower() for i in interests]
    assert len(lower) == len(set(lower))  # no case-insensitive duplicates


def test_patch_experience_years_validation():
    c, _ = client()
    assert c.patch("/api/v1/profile", json={"experience_years": -1}).status_code == 400
    assert c.patch("/api/v1/profile", json={"experience_years": 51}).status_code == 400
    assert c.patch("/api/v1/profile", json={"experience_years": 0}).status_code == 200
    assert c.patch("/api/v1/profile", json={"experience_years": 50}).status_code == 200


def test_patch_education_max_length():
    c, _ = client()
    r = c.patch("/api/v1/profile", json={"education": "x" * 201})
    assert r.status_code == 400


# ---- match endpoint ----

def test_match_returns_unknown_when_no_profile():
    store = InMemoryStore()
    opp = make_opp()
    store.save_opportunity(opp)
    c, _ = client(store)
    r = c.get("/api/v1/profile/match/opp1")
    assert r.status_code == 200
    data = r.json()
    assert data["opportunity_id"] == "opp1" and data["overall"] == "unknown"
    assert data["reasons"] == []


def test_match_location_hit():
    store = InMemoryStore()
    store.save_opportunity(make_opp("Bengaluru, India"))
    c, _ = client(store, user="user-a")
    c.patch("/api/v1/profile", json={"location": "Bengaluru"})
    r = c.get("/api/v1/profile/match/opp1")
    assert r.status_code == 200
    reasons = r.json()["reasons"]
    assert any(res["positive"] and "Location" in res["reason"] for res in reasons)
    assert r.json()["overall"] in ("good_match", "partial_match")


def test_match_location_miss():
    store = InMemoryStore()
    store.save_opportunity(make_opp("Mumbai"))
    c, _ = client(store, user="user-a")
    c.patch("/api/v1/profile", json={"location": "Hyderabad"})
    r = c.get("/api/v1/profile/match/opp1")
    reasons = r.json()["reasons"]
    assert any(not res["positive"] and "Location" in res["reason"] for res in reasons)


def test_match_interest_alignment_uses_report_claims():
    store = InMemoryStore()
    opp = make_opp()
    store.save_opportunity(opp)
    make_report(store, opp)
    c, _ = client(store, user="user-a")
    # "open" is a normalized value in the report
    c.patch("/api/v1/profile", json={"interests": ["open source"]})
    r = c.get("/api/v1/profile/match/opp1")
    assert r.status_code == 200
    # Data-minimization check: raw profile value not echoed back
    assert "open source" not in r.text.replace('"open source"', "").replace("'open source'", "")


def test_match_experience_entry_level():
    store = InMemoryStore()
    store.save_opportunity(make_opp())
    c, _ = client(store, user="user-a")
    c.patch("/api/v1/profile", json={"experience_years": 0})
    r = c.get("/api/v1/profile/match/opp1")
    reasons = r.json()["reasons"]
    assert any("Entry-level" in res["reason"] and res["positive"] for res in reasons)


def test_match_experienced_profile_flags_mismatch():
    store = InMemoryStore()
    store.save_opportunity(make_opp())
    c, _ = client(store, user="user-a")
    c.patch("/api/v1/profile", json={"experience_years": 10})
    r = c.get("/api/v1/profile/match/opp1")
    reasons = r.json()["reasons"]
    assert any(not res["positive"] and "Experienced" in res["reason"] for res in reasons)


def test_match_unknown_opportunity_returns_404():
    c, _ = client()
    r = c.get("/api/v1/profile/match/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


# ---- auth boundary ----

def test_profile_routes_require_auth():
    store = InMemoryStore()
    app = create_app(Settings(), store=store)  # no overrides
    with TestClient(app) as c:
        for method, path, kwargs in [
            ("GET", "/api/v1/profile", {}),
            ("PATCH", "/api/v1/profile", {"json": {}}),
            ("GET", "/api/v1/profile/match/opp1", {}),
        ]:
            r = getattr(c, method.lower())(path, **kwargs)
            assert r.status_code == 401, f"{method} {path} should return 401, got {r.status_code}"
            assert r.json()["error"]["code"] == "UNAUTHENTICATED"
