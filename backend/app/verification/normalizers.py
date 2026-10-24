"""Per-claim-type value normalization. Anything not clearly parseable is 'uncertain' (never guessed)."""
import re
from dataclasses import dataclass

from app.discovery.normalize import canonicalize_url
from app.schemas.enums import ClaimType
from app.verification.dates import parse_date_text

TEXT_TYPES = {ClaimType.location, ClaimType.eligibility, ClaimType.organization, ClaimType.other}


@dataclass(frozen=True)
class Normalized:
    value: str | None
    certain: bool
    reason: str | None = None


_CLOSED = re.compile(r"\b(closed|not (?:currently )?(?:open|accepting)|no longer accepting|expired)\b", re.I)
_FUTURE = re.compile(r"\b(opens? (?:on|in)|will open|opening|coming soon|upcoming)\b", re.I)
_OPEN = re.compile(r"\b(open|accepting|rolling|apply now|now hiring)\b", re.I)

_CUR = {"₹": "INR", "rs": "INR", "inr": "INR", "$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR",
        "£": "GBP", "gbp": "GBP"}
_AMT = re.compile(r"(₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|lakhs?|lacs?)?", re.I)
_PER = re.compile(r"(?:per|/|a|each)\s*(month|mo|year|yr|annum|week|wk|hour|hr)\b|"
                  r"\b(monthly|yearly|annually|weekly|hourly)\b|\bp\.?m\b", re.I)
_PERIODS = {"month": "month", "mo": "month", "monthly": "month", "pm": "month", "pm.": "month",
            "year": "year", "yr": "year", "annum": "year", "yearly": "year", "annually": "year",
            "week": "week", "wk": "week", "weekly": "week", "hour": "hour", "hr": "hour", "hourly": "hour"}
_UNPAID = re.compile(r"\b(unpaid|no stipend)\b", re.I)
_DUR = re.compile(r"(\d+(?:\.\d+)?)\s*(weeks?|wks?|months?|mos?|days?|years?|yrs?)\b", re.I)
_RANGE = re.compile(r"\d\s*(?:-|–|to)\s*\d", re.I)
_UNITS = {"w": "week", "m": "month", "d": "day", "y": "year"}


def norm_text(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", s.casefold()).split())


def _num(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _status(raw: str) -> Normalized:
    if _FUTURE.search(raw):
        return Normalized(None, False, "status wording refers to a future or unclear state")
    if _CLOSED.search(raw):
        return Normalized("closed", True)
    if _OPEN.search(raw):
        return Normalized("open", True)
    return Normalized(None, False, "status not recognized")


def _url(raw: str) -> Normalized:
    candidate = raw.strip()
    if "://" not in candidate and "." in candidate and " " not in candidate:
        candidate = "https://" + candidate
    try:
        return Normalized(canonicalize_url(candidate), True)
    except ValueError:
        return Normalized(None, False, "not a valid URL")


def _stipend(raw: str) -> Normalized:
    if _UNPAID.search(raw):
        return Normalized("unpaid", True)
    amounts = list(_AMT.finditer(raw))
    if len(amounts) != 1:
        return Normalized(None, False, "no single amount found (ranges are not normalized)")
    m = amounts[0]
    cur = _CUR.get((m.group(1) or "").lower().rstrip("."))
    if not cur:
        return Normalized(None, False, "currency not stated")
    amount = float(m.group(2).replace(",", ""))
    mult = (m.group(3) or "").lower()
    amount *= 1000 if mult == "k" else 100000 if mult else 1
    per = _PER.search(raw)
    period = _PERIODS.get(next(g for g in per.groups() if g).lower()) if per else None
    if not period:
        return Normalized(None, False, "pay period not stated")
    return Normalized(f"{cur} {_num(amount)}/{period}", True)


def _duration(raw: str) -> Normalized:
    found = _DUR.findall(raw)
    if len(found) != 1 or _RANGE.search(raw):
        return Normalized(None, False, "no single duration found")
    n, unit = float(found[0][0]), _UNITS[found[0][1][0].lower()]
    return Normalized(f"{_num(n)} {unit}{'' if n == 1 else 's'}", True)


def normalize(claim_type: ClaimType, raw: str) -> Normalized:
    raw = raw.strip()
    if not raw:
        return Normalized(None, False, "empty value")
    if claim_type in (ClaimType.deadline, ClaimType.start_date):
        p = parse_date_text(raw)
        if p.is_rolling and claim_type == ClaimType.deadline:
            return Normalized("rolling", True)
        if p.is_certain and p.date:
            return Normalized(p.date.isoformat(), True, p.reason)
        return Normalized(None, False, p.reason)
    if claim_type == ClaimType.application_status:
        return _status(raw)
    if claim_type == ClaimType.application_url:
        return _url(raw)
    if claim_type == ClaimType.stipend:
        return _stipend(raw)
    if claim_type == ClaimType.duration:
        return _duration(raw)
    text = norm_text(raw)
    return Normalized(text, True) if text else Normalized(None, False, "empty value")


def compatible(claim_type: ClaimType, a: str, b: str) -> bool:
    """Structured values must match exactly. Free text matches if equal or one is contained in the
    other (word-wise). Aliases (e.g. Bangalore/Bengaluru) are NOT resolved, so they show as differences."""
    if a == b:
        return True
    if claim_type in TEXT_TYPES:
        ta, tb = set(a.split()), set(b.split())
        return ta <= tb or tb <= ta
    return False