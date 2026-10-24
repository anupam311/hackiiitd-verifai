"""Small validators shared by schemas."""
import datetime as dt
from urllib.parse import urlsplit


def validate_http_url(value: str) -> str:
    value = value.strip()
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("URL must use http(s) and include a host")
    return value


def ensure_utc(value: dt.datetime) -> dt.datetime:
    """Reject naive datetimes (no guessing) and convert aware ones to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(dt.timezone.utc)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)