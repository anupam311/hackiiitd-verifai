import datetime as dt

import pytest

from app.schemas.enums import (ClaimType as C, OpportunityStatus, RetrievalOutcome, SourceType as T,
                               VerificationStatus as S)
from app.schemas.source import SourceObservation
from app.verification.dates import is_past, parse_date_text
from app.verification.models import EvidenceItem, EvidenceRole
from app.verification.normalizers import compatible, normalize
from app.verification.policy import (derive_opportunity_status, summarize, verify_claim,
                                     verify_opportunity)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 6, 1, 12, tzinfo=UTC)


def obs(domain="careers.example.com", stype=T.official, hours=1.0, outcome=RetrievalOutcome.ok):
    at = NOW - dt.timedelta(hours=hours)
    return SourceObservation(id=f"{domain}-{hours}", url=f"https://{domain}/p", domain=domain,
                             source_type=stype, retrieved_at=at, retrieval_outcome=outcome)


def ev(value, claim=C.deadline, conf=0.9, **kw):
    return EvidenceItem(claim_type=claim, extracted_value=value, excerpt=value, evidence_locator="text:0-1",
                        confidence=conf, observation=obs(**kw))


def verify(claim, evidence, sources=()):
    return verify_claim(claim, evidence, list(sources), NOW)


# ---- dates ----
@pytest.mark.parametrize("raw,iso", [
    ("June 15, 2026", "2026-06-15"), ("15th June 2026", "2026-06-15"), ("Jun 15 2026", "2026-06-15"),
    ("2026-06-15", "2026-06-15"), ("15/06/2026", "2026-06-15"), ("06/15/2026", "2026-06-15"),
    ("Deadline: 15 Jun 2026, 11:59 PM UTC+05:30", "2026-06-15"), ("12/12/2026", "2026-12-12"),
])
def test_certain_dates(raw, iso):
    p = parse_date_text(raw)
    assert p.is_certain and p.date.isoformat() == iso


@pytest.mark.parametrize("raw", ["June 15", "03/04/2026", "June 2026", "Feb 30, 2026", "soon",
                                 "June 15, 2026 or July 1, 2026", "Jun 25"])
def test_ambiguous_dates_are_never_guessed(raw):
    p = parse_date_text(raw)
    assert not p.is_certain and p.date is None and p.reason and p.raw_text == raw


def test_timezone_handling_and_rolling():
    assert parse_date_text("June 15, 2026 UTC+05:30").timezone_name == "UTC+05:30"
    ist = parse_date_text("June 15, 2026 11:59 PM IST")
    assert ist.timezone_name is None and ist.reason == "timezone abbreviation not interpreted"
    assert parse_date_text("Rolling basis").is_rolling


def test_is_past_has_timezone_buffer():
    p = parse_date_text("2026-05-31")
    assert is_past(p, NOW) is False  # within 1-day buffer
    assert is_past(parse_date_text("2026-05-01"), NOW) is True
    assert is_past(parse_date_text("June 15"), NOW) is None


# ---- normalizers ----
@pytest.mark.parametrize("claim,raw,expected", [
    (C.stipend, "₹1,20,000 / month", "INR 120000/month"), (C.stipend, "$5,000 per month", "USD 5000/month"),
    (C.stipend, "INR 1.2 lakh monthly", "INR 120000/month"), (C.stipend, "Unpaid", "unpaid"),
    (C.duration, "12 weeks", "12 weeks"), (C.duration, "1 month", "1 month"),
    (C.application_status, "Open (rolling applications)", "open"),
    (C.application_status, "Applications closed", "closed"), (C.application_status, "Not accepting", "closed"),
    (C.application_url, "careers.example.com/students/?utm_x=1", "https://careers.example.com/students"),
    (C.deadline, "Rolling", "rolling"),
])
def test_normalizers(claim, raw, expected):
    n = normalize(claim, raw)
    assert n.certain and n.value == expected


@pytest.mark.parametrize("claim,raw", [
    (C.stipend, "₹80,000 - ₹1,20,000 per month"), (C.stipend, "1000 per month"), (C.stipend, "₹5000"),
    (C.duration, "10-12 weeks"), (C.application_status, "Opens on March 1"), (C.application_status, "TBD"),
])
def test_uncertain_values(claim, raw):
    assert not normalize(claim, raw).certain


def test_compatibility():
    assert compatible(C.location, "bengaluru india", "bengaluru")
    assert not compatible(C.location, "bengaluru india", "hyderabad india")
    assert not compatible(C.stipend, "INR 1/month", "INR 2/month")


# ---- statuses ----
def test_confirmed_by_fresh_official_source():
    v = verify(C.deadline, [ev("June 15, 2026")])
    assert v.status == S.confirmed and v.normalized_value == "2026-06-15"
    assert "careers.example.com" in v.explanation and "2026-06-01" in v.explanation and v.next_step


def test_aggregator_cannot_override_official_but_discrepancy_stays_visible():
    v = verify(C.stipend, [ev("₹1,20,000 / month", C.stipend),
                           ev("₹1,10,000 / month", C.stipend, domain="glassdoor.com", stype=T.aggregator)])
    assert v.status == S.confirmed and v.normalized_value == "INR 120000/month"
    roles = {e.is_authoritative: e.role for e in v.evidence}
    assert roles[False] == EvidenceRole.discrepant and roles[True] == EvidenceRole.supports
    assert "glassdoor.com" in v.explanation or "non-authoritative" in v.explanation
    assert summarize([v]).discrepancies == 1


def test_official_sources_disagreeing_is_conflicting():
    v = verify(C.deadline, [ev("June 15, 2026"), ev("June 20, 2026", domain="jobs.example.com", stype=T.employer)])
    assert v.status == S.conflicting and v.normalized_value is None and v.needs_review
    assert {e.role for e in v.evidence} == {EvidenceRole.conflicting}
    assert "2026-06" not in v.explanation and "June 15, 2026" in v.explanation and "June 20, 2026" in v.explanation


def test_stale_official_evidence_is_downgraded():
    v = verify(C.application_status, [ev("Open", C.application_status, hours=72)])  # 2-day window
    assert v.status == S.partially_confirmed and v.stale and "Recheck" in v.next_step
    assert verify(C.location, [ev("Bengaluru", C.location, hours=72)]).status == S.confirmed  # 60-day window


def test_ambiguous_official_deadline_is_partial_and_ambiguous_weak_is_unverified():
    v = verify(C.deadline, [ev("June 15")])
    assert v.status == S.partially_confirmed and v.normalized_value is None and "ambiguous" in v.explanation
    w = verify(C.deadline, [ev("June 15", domain="x.com", stype=T.aggregator)])
    assert w.status == S.unverified


def test_non_authoritative_only_never_confirms():
    one = verify(C.stipend, [ev("$5,000 per month", C.stipend, domain="a.com", stype=T.aggregator)])
    assert one.status == S.unverified
    two = verify(C.stipend, [ev("$5,000 per month", C.stipend, domain="a.com", stype=T.aggregator),
                             ev("$5,000/month", C.stipend, domain="b.com", stype=T.community)])
    assert two.status == S.partially_confirmed
    split = verify(C.stipend, [ev("$5,000 per month", C.stipend, domain="a.com", stype=T.aggregator),
                               ev("$4,000/month", C.stipend, domain="b.com", stype=T.community)])
    assert split.status == S.conflicting


def test_free_text_differences_need_review_not_conflict():
    v = verify(C.eligibility, [ev("BE/BTech in CS", C.eligibility), ev("Any graduate", C.eligibility, domain="j.example.com", stype=T.employer)])
    assert v.status == S.partially_confirmed and v.needs_review
    loc = verify(C.location, [ev("Bengaluru", C.location), ev("Hyderabad", C.location, domain="j.example.com", stype=T.employer)])
    assert loc.status == S.conflicting


def test_low_extraction_confidence_from_official_source_is_not_decisive():
    v = verify(C.deadline, [ev("June 15, 2026", conf=0.2)])
    assert v.status == S.partially_confirmed and v.normalized_value is None


def test_failed_retrieval_is_unavailable_never_closed():
    failed = [obs(outcome=RetrievalOutcome.not_found), obs("x.com", T.aggregator, outcome=RetrievalOutcome.blocked)]
    v = verify(C.application_status, [], failed)
    assert v.status == S.unavailable and "not evidence" in v.explanation
    assert derive_opportunity_status([v]) == OpportunityStatus.unknown
    assert verify(C.deadline, [], []).status == S.unavailable


def test_evidence_from_failed_observations_is_ignored():
    bad = ev("June 15, 2026")
    bad.observation = obs(outcome=RetrievalOutcome.blocked)
    assert verify(C.deadline, [bad]).status == S.unavailable


def test_past_deadline_does_not_change_status_or_close_opportunity():
    dl = verify(C.deadline, [ev("May 1, 2026")])
    assert dl.status == S.confirmed and "does not show applications are closed" in dl.explanation
    st = verify(C.application_status, [ev("Open", C.application_status)])
    assert derive_opportunity_status([dl, st]) == OpportunityStatus.open
    assert derive_opportunity_status([dl]) == OpportunityStatus.unknown


def test_only_confirmed_status_claim_sets_opportunity_status():
    closed = verify(C.application_status, [ev("Applications closed", C.application_status)])
    assert derive_opportunity_status([closed]) == OpportunityStatus.closed
    stale = verify(C.application_status, [ev("Open", C.application_status, hours=100)])
    assert derive_opportunity_status([stale]) == OpportunityStatus.unknown


def test_verify_opportunity_covers_core_and_found_claims_and_summary_formula():
    vs = verify_opportunity([ev("June 15, 2026"), ev("12 weeks", C.duration)], [], NOW)
    kinds = [v.claim_type for v in vs]
    assert set(kinds) == {C.deadline, C.application_status, C.application_url, C.eligibility, C.duration}
    s = summarize(vs)
    assert s.total == 5 and s.counts["confirmed"] == 2 and s.counts["unavailable"] == 3
    assert s.score_percent == 40.0 and "not a probability" in s.formula
    assert summarize([]).score_percent is None


def test_agreeing_non_authoritative_source_is_support_not_discrepancy():
    v = verify(C.duration, [ev("12 weeks", C.duration),
                            ev("12 weeks", C.duration, domain="a.com", stype=T.aggregator)])
    assert v.status == S.confirmed and {e.role for e in v.evidence} == {EvidenceRole.supports}
    assert summarize([v]).discrepancies == 0