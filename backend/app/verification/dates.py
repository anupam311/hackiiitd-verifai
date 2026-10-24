"""Deterministic date parsing. Never guesses a year, a day/month order, or which of several dates applies."""
import datetime as dt
import re
from dataclasses import dataclass

_M = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
      r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                       "oct", "nov", "dec"], 1)}
_ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)\b", re.I)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MDY = re.compile(rf"\b{_M}\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.I)
_DMY = re.compile(rf"\b(\d{{1,2}})\s+{_M}\.?,?\s+(\d{{4}})\b", re.I)
_NUM = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b")
_PARTIAL = re.compile(rf"\b{_M}\.?\s+\d{{1,2}}\b|\b\d{{1,2}}\s+{_M}\b|\b{_M}\.?\s+\d{{4}}\b", re.I)
_ROLLING = re.compile(r"\b(rolling|until (?:the position is )?filled|ongoing|no deadline)\b", re.I)
_TZ = re.compile(r"\b(?:UTC|GMT)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?\b|\b(UTC|GMT)\b")
_ABBR = re.compile(r"\b(IST|PST|PDT|EST|EDT|CST|CDT|MST|MDT|CET|CEST|BST|JST|AEST)\b")


@dataclass(frozen=True)
class ParsedDate:
    raw_text: str
    date: dt.date | None = None
    is_certain: bool = False
    is_rolling: bool = False
    timezone_name: str | None = None
    reason: str | None = None  # why it is uncertain


def _mk(y: int, m: int, d: int) -> dt.date | None:
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def _timezone(text: str) -> tuple[str | None, str | None]:
    m = _TZ.search(text)
    if m:
        if m.group(4):
            return "UTC", None
        hh, mm = int(m.group(2)), int(m.group(3) or 0)
        return f"UTC{m.group(1)}{hh:02d}:{mm:02d}", None
    if _ABBR.search(text):  # abbreviations like IST are ambiguous worldwide: not interpreted
        return None, "timezone abbreviation not interpreted"
    return None, None


def parse_date_text(raw: str) -> ParsedDate:
    text = _ORDINAL.sub("", raw.strip())
    tz, tz_note = _timezone(text)
    if _ROLLING.search(text):
        return ParsedDate(raw, is_rolling=True, timezone_name=tz, reason="rolling or open-ended")

    dates: list[dt.date | None] = []  # None marks a match that is ambiguous or invalid
    for m in _ISO.finditer(text):
        dates.append(_mk(int(m[1]), int(m[2]), int(m[3])))
    for m in _MDY.finditer(text):
        dates.append(_mk(int(m[3]), _MONTHS[m[1][:3].lower()], int(m[2])))
    for m in _DMY.finditer(text):
        dates.append(_mk(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1])))
    for m in _NUM.finditer(text):
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12 or a == b:
            dates.append(_mk(y, b, a))
        elif b > 12:
            dates.append(_mk(y, a, b))
        else:
            dates.append(None)  # 03/04/2026 could be 3 April or 4 March

    if not dates:
        reason = "year missing or day not stated" if _PARTIAL.search(text) else "no recognizable date"
        return ParsedDate(raw, timezone_name=tz, reason=reason)
    if None in dates:
        return ParsedDate(raw, timezone_name=tz, reason="ambiguous or invalid date format")
    if len(set(dates)) > 1:
        return ParsedDate(raw, timezone_name=tz, reason="multiple different dates")
    return ParsedDate(raw, date=dates[0], is_certain=True, timezone_name=tz, reason=tz_note)


def is_past(parsed: ParsedDate, now: dt.datetime) -> bool | None:
    """True only when the date has clearly passed (1-day buffer covers every UTC offset).
    A past date is never proof that applications are closed."""
    if parsed.date is None:
        return None
    return now.astimezone(dt.timezone.utc).date() > parsed.date + dt.timedelta(days=1)