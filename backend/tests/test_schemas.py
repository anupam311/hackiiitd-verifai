import datetime as dt

import pytest
from pydantic import ValidationError

from app.schemas.claim import Claim, ClaimEvidence
from app.schemas.discovery import DiscoverySearchRequest
from app.schemas.enums import OpportunityStatus, VerificationStatus
from app.schemas.opportunity import DeadlineInfo, Opportunity
from app.schemas.source import SourceObservation

UTC = dt.timezone.utc


def opp(**kw):
    base = dict(id="o1", title="Test role", organization="Example Org", category="internship",
                canonical_url="https://example.com/apply", is_demo=True)
    return Opportunity(**{**base, **kw})


def obs(**kw):
    base = dict(id="s1", url="https://example.com/a", domain="example.com",
                retrieved_at=dt.datetime(2026, 1, 1, tzinfo=UTC))
    return SourceObservation(**{**base, **kw})


def test_opportunity_defaults_to_unknown_status():
    assert opp().status == OpportunityStatus.unknown


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "ftp://example.com", "example.com", "https://"])
def test_non_http_urls_rejected(bad):
    with pytest.raises(ValidationError):
        opp(canonical_url=bad)


def test_certain_deadline_needs_a_date():
    with pytest.raises(ValidationError):
        DeadlineInfo(raw_text="June 15", is_certain=True)
    assert DeadlineInfo(raw_text="June 15").date is None  # ambiguous year stays uncertain


def test_naive_datetime_rejected_and_aware_converted_to_utc():
    with pytest.raises(ValidationError):
        obs(retrieved_at=dt.datetime(2026, 1, 1))
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    o = obs(retrieved_at=dt.datetime(2026, 1, 1, 5, 30, tzinfo=ist))
    assert o.retrieved_at == dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert o.retrieved_at.utcoffset() == dt.timedelta(0)


def test_domain_must_match_url_host():
    with pytest.raises(ValidationError):
        obs(domain="other.com")


def test_claim_requires_explanation_and_valid_status():
    with pytest.raises(ValidationError):
        Claim(id="c1", opportunity_id="o1", claim_type="deadline", explanation="")
    with pytest.raises(ValidationError):
        Claim(id="c1", opportunity_id="o1", claim_type="deadline", status="maybe", explanation="x")
    assert Claim(id="c1", opportunity_id="o1", claim_type="deadline", explanation="x").status \
        == VerificationStatus.unverified


def test_evidence_requires_locator_and_bounded_confidence():
    base = dict(claim_id="c1", source_observation_id="s1", extracted_value="v", confidence=0.5,
                evidence_locator="h1 > p:2", extraction_method="m", schema_version="1")
    ClaimEvidence(**base)
    with pytest.raises(ValidationError):
        ClaimEvidence(**{**base, "evidence_locator": ""})
    with pytest.raises(ValidationError):
        ClaimEvidence(**{**base, "confidence": 1.5})


def test_search_request_limits():
    assert DiscoverySearchRequest(query="x").limit == 20
    for bad in (0, 51):
        with pytest.raises(ValidationError):
            DiscoverySearchRequest(query="x", limit=bad)
    with pytest.raises(ValidationError):
        DiscoverySearchRequest(query="")