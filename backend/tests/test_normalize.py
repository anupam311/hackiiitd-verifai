import datetime as dt

import pytest

from app.discovery.base import RawSourceRecord
from app.discovery.normalize import (canonicalize_url, classify_source_type, derive_outcome,
                                     normalize_record, normalize_records)
from app.schemas.enums import Freshness, RetrievalOutcome, SourceType

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 6, 1, 12, tzinfo=UTC)


def raw(url="https://example.com/a", at=NOW - dt.timedelta(hours=1), **kw):
    return RawSourceRecord(url=url, retrieved_at=at, **kw)


@pytest.mark.parametrize("given,expected", [
    ("HTTPS://Example.COM:443/jobs/?utm_source=x&b=2&a=1#top", "https://example.com/jobs?a=1&b=2"),
    ("http://example.com:80", "http://example.com/"),
    ("https://user:pw@example.com/p", "https://example.com/p"),
    ("https://example.com:8443/p/", "https://example.com:8443/p"),
    ("https://example.com/p?gclid=1&id=7", "https://example.com/p?id=7"),
])
def test_canonicalize_url(given, expected):
    assert canonicalize_url(given) == expected


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "ftp://example.com", "not a url", "https://"])
def test_canonicalize_rejects_unsupported(bad):
    with pytest.raises(ValueError):
        canonicalize_url(bad)


def test_source_type_rules():
    assert classify_source_type("www.linkedin.com", SourceType.official) == SourceType.aggregator
    assert classify_source_type("reddit.com", None) == SourceType.community
    assert classify_source_type("example.com", SourceType.official) == SourceType.official
    assert classify_source_type("example.com", None) == SourceType.other  # never guessed official


@pytest.mark.parametrize("status,expected", [
    (200, RetrievalOutcome.ok), (404, RetrievalOutcome.not_found), (410, RetrievalOutcome.not_found),
    (403, RetrievalOutcome.blocked), (429, RetrievalOutcome.blocked),
    (500, RetrievalOutcome.http_error), (None, RetrievalOutcome.unknown), (302, RetrievalOutcome.unknown),
])
def test_derive_outcome(status, expected):
    assert derive_outcome(status, None) == expected


def test_outcome_hint_wins():
    assert derive_outcome(None, RetrievalOutcome.timeout) == RetrievalOutcome.timeout


def test_freshness():
    assert normalize_record(raw(http_status=200), now=NOW).freshness == Freshness.fresh
    old = raw(http_status=200, at=NOW - dt.timedelta(days=30))
    assert normalize_record(old, now=NOW).freshness == Freshness.stale
    failed = raw(http_status=404)
    assert normalize_record(failed, now=NOW).freshness == Freshness.unknown


def test_timestamps_converted_to_utc_and_bad_ones_rejected():
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    o = normalize_record(raw(at=dt.datetime(2026, 6, 1, 15, 30, tzinfo=ist), http_status=200), now=NOW)
    assert o.retrieved_at == dt.datetime(2026, 6, 1, 10, tzinfo=UTC)
    with pytest.raises(ValueError):
        normalize_record(raw(at=dt.datetime(2026, 5, 1)), now=NOW)  # naive
    with pytest.raises(ValueError):
        normalize_record(raw(at=NOW + dt.timedelta(days=1)), now=NOW)  # future


def test_content_hash_and_deterministic_id():
    a = normalize_record(raw(content_text="hello"), now=NOW)
    b = normalize_record(raw(content_text="hello"), now=NOW)
    assert a.content_hash and a.content_hash == b.content_hash and a.id == b.id
    assert normalize_record(raw(content_hash="given"), now=NOW).content_hash == "given"


def test_bad_records_rejected_without_storing_urls():
    res = normalize_records([raw(), raw(url="javascript:x"), raw(at=dt.datetime(2026, 1, 1))], now=NOW)
    assert len(res.observations) == 1
    assert [r.index for r in res.rejected] == [1, 2]
    assert all("javascript" not in r.reason for r in res.rejected)


def test_dedup_keeps_newest_success_and_failure_does_not_hide_it():
    t = lambda h: NOW - dt.timedelta(hours=h)  # noqa: E731
    recs = [
        raw("https://example.com/a?utm_x=1", t(5), http_status=200),
        raw("https://example.com/a/", t(3), http_status=200),
        raw("https://example.com/a#frag", t(1), http_status=403),
        raw("https://example.com/b", t(2), http_status=404),
    ]
    res = normalize_records(recs, now=NOW)
    assert len(res.observations) == 2 and res.duplicates_dropped == 2
    a = next(o for o in res.observations if o.url.endswith("/a"))
    assert a.retrieval_outcome == RetrievalOutcome.ok and a.retrieved_at == t(3)
    b = next(o for o in res.observations if o.url.endswith("/b"))
    assert b.retrieval_outcome == RetrievalOutcome.not_found  # kept as a visible failed observation