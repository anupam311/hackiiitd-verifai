"""Turn untrusted RawSourceRecords into validated, de-duplicated SourceObservations."""
import datetime as dt
import hashlib
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.discovery.base import RawSourceRecord
from app.schemas.enums import Freshness, RetrievalOutcome, SourceType
from app.schemas.source import SourceObservation

DEFAULT_MAX_AGE = dt.timedelta(days=7)  # observation-level only; claim-level freshness comes later
CLOCK_SKEW = dt.timedelta(minutes=5)

_TRACKING = {"gclid", "fbclid", "mc_cid", "mc_eid", "igshid"}
_AGGREGATORS = ("linkedin.com", "glassdoor.com", "indeed.com", "naukri.com", "internshala.com")
_COMMUNITY = ("reddit.com", "quora.com", "x.com", "twitter.com", "facebook.com", "t.me")


def _is_tracking(key: str) -> bool:
    k = key.lower()
    return k.startswith("utm_") or k in _TRACKING


def canonicalize_url(url: str) -> str:
    """Lowercase host, drop credentials/fragment/default port/tracking params, sort query."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = parts.hostname
    if scheme not in ("http", "https") or not host:
        raise ValueError("unsupported URL")
    try:
        port = parts.port
    except ValueError:
        raise ValueError("invalid port") from None
    if ":" in host:
        host = f"[{host}]"
    default = 80 if scheme == "http" else 443
    netloc = host if port in (None, default) else f"{host}:{port}"
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(pairs)), ""))


def _domain_in(domain: str, names: tuple[str, ...]) -> bool:
    return any(domain == n or domain.endswith("." + n) for n in names)


def classify_source_type(domain: str, hint: SourceType | None) -> SourceType:
    """Aggregator/community domains can never be 'official'. Without a hint we do NOT guess 'official'."""
    if _domain_in(domain, _AGGREGATORS):
        return SourceType.aggregator
    if _domain_in(domain, _COMMUNITY):
        return SourceType.community
    return hint or SourceType.other


def derive_outcome(status: int | None, hint: RetrievalOutcome | None) -> RetrievalOutcome:
    if hint is not None:
        return hint
    if status is None:
        return RetrievalOutcome.unknown
    if 200 <= status < 300:
        return RetrievalOutcome.ok
    if status in (404, 410):
        return RetrievalOutcome.not_found
    if status in (401, 403, 429):
        return RetrievalOutcome.blocked
    if status >= 400:
        return RetrievalOutcome.http_error
    return RetrievalOutcome.unknown  # 1xx/3xx: unresolved, not evidence of anything


def compute_freshness(outcome: RetrievalOutcome, retrieved_at: dt.datetime, now: dt.datetime,
                      max_age: dt.timedelta) -> Freshness:
    if outcome != RetrievalOutcome.ok:
        return Freshness.unknown
    return Freshness.fresh if now - retrieved_at <= max_age else Freshness.stale


def normalize_record(raw: RawSourceRecord, *, now: dt.datetime,
                     max_age: dt.timedelta = DEFAULT_MAX_AGE) -> SourceObservation:
    """Raises ValueError when the record cannot be trusted (bad URL, naive or future timestamp)."""
    url = canonicalize_url(raw.url)
    if raw.retrieved_at.tzinfo is None or raw.retrieved_at.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone-aware")
    retrieved_at = raw.retrieved_at.astimezone(dt.timezone.utc)
    if retrieved_at > now + CLOCK_SKEW:
        raise ValueError("retrieved_at is in the future")
    domain = urlsplit(url).hostname or ""
    outcome = derive_outcome(raw.http_status, raw.retrieval_outcome)
    content_hash = raw.content_hash or (
        hashlib.sha256(raw.content_text.encode("utf-8")).hexdigest() if raw.content_text else None
    )
    obs_id = "obs_" + hashlib.sha256(f"{url}|{retrieved_at.isoformat()}".encode()).hexdigest()[:16]
    return SourceObservation(
        id=obs_id, url=url, domain=domain,
        source_type=classify_source_type(domain, raw.source_type_hint),
        retrieved_at=retrieved_at, http_status=raw.http_status, retrieval_outcome=outcome,
        content_hash=content_hash, freshness=compute_freshness(outcome, retrieved_at, now, max_age),
    )


@dataclass
class RejectedRecord:
    index: int
    reason: str  # raw URLs are not stored: they can carry tokens


@dataclass
class NormalizationResult:
    observations: list[SourceObservation] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)
    duplicates_dropped: int = 0
    content_by_observation: dict[str, str] = field(default_factory=dict)  # untrusted page text


def normalize_records(records: list[RawSourceRecord], *, now: dt.datetime | None = None,
                      max_age: dt.timedelta = DEFAULT_MAX_AGE) -> NormalizationResult:
    """Normalize and de-duplicate by canonical URL.

    Per URL we keep the newest successful observation; if none succeeded, the newest overall.
    A later failed fetch therefore never hides an earlier successful one.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    result = NormalizationResult()
    groups: dict[str, list[SourceObservation]] = {}
    texts: dict[str, str] = {}
    for i, raw in enumerate(records):
        try:
            obs = normalize_record(raw, now=now, max_age=max_age)
        except ValueError as exc:
            result.rejected.append(RejectedRecord(i, str(exc)))
            continue
        groups.setdefault(obs.url, []).append(obs)
        if raw.content_text:
            texts[obs.id] = raw.content_text
    for group in groups.values():
        ok = [o for o in group if o.retrieval_outcome == RetrievalOutcome.ok]
        kept = max(ok or group, key=lambda o: o.retrieved_at)
        result.observations.append(kept)
        if kept.id in texts:
            result.content_by_observation[kept.id] = texts[kept.id]
        result.duplicates_dropped += len(group) - 1
    return result