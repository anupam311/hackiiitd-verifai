"""Deterministic claim-level verification (docs/verification_policy.md). No LLM involved."""
import datetime as dt
from dataclasses import dataclass

from app.schemas.enums import (ClaimType, OpportunityStatus, RetrievalOutcome, SourceType,
                               VerificationStatus as S)
from app.schemas.source import SourceObservation
from app.verification.dates import ParsedDate, is_past
from app.verification.models import (ClaimVerdict, EvidenceAssessment, EvidenceItem, EvidenceRole,
                                     VerificationSummary)
from app.verification.normalizers import Normalized, compatible, normalize

AUTHORITATIVE = {SourceType.official, SourceType.employer, SourceType.institution}
MIN_CONFIDENCE = 0.5
CORE_CLAIMS = (ClaimType.deadline, ClaimType.application_status, ClaimType.application_url,
               ClaimType.eligibility)
FRESHNESS_DAYS = {
    ClaimType.application_status: 2, ClaimType.deadline: 7, ClaimType.application_url: 14,
    ClaimType.eligibility: 30, ClaimType.stipend: 30, ClaimType.duration: 30, ClaimType.start_date: 30,
    ClaimType.location: 60, ClaimType.organization: 180, ClaimType.other: 30,
}
# Free-text claims can't be judged "materially different" deterministically: differences need review.
REVIEW_NOT_CONFLICT = {ClaimType.eligibility, ClaimType.other}
SCORE_WEIGHTS = {S.confirmed: 1.0, S.partially_confirmed: 0.5}
FORMULA = ("Coverage score = 100 x (confirmed x 1 + partially confirmed x 0.5) / claims evaluated. "
           "Conflicting, unverified and unavailable claims score 0. It measures how much of the claim "
           "set is supported by evidence; it is not a probability that the opportunity is genuine.")


@dataclass
class _Item:
    ev: EvidenceItem
    norm: Normalized
    auth: bool
    fresh: bool

    @property
    def decisive(self) -> bool:
        return self.norm.certain and self.ev.confidence >= MIN_CONFIDENCE

    @property
    def obs(self) -> SourceObservation:
        return self.ev.observation


def is_fresh(claim_type: ClaimType, retrieved_at: dt.datetime, now: dt.datetime) -> bool:
    return now - retrieved_at <= dt.timedelta(days=FRESHNESS_DAYS[claim_type])


def _group(claim_type: ClaimType, items: list[_Item]) -> list[list[_Item]]:
    groups: list[list[_Item]] = []
    for it in items:
        for g in groups:
            if compatible(claim_type, g[0].norm.value or "", it.norm.value or ""):
                g.append(it)
                break
        else:
            groups.append([it])
    return groups


def _src(it: _Item) -> str:
    return f"{it.obs.domain} ({it.obs.source_type.value})"


def _stamp(it: _Item) -> str:
    return it.obs.retrieved_at.strftime("%Y-%m-%d %H:%MZ")


def _past_note(claim_type: ClaimType, value: str | None, now: dt.datetime) -> str:
    if claim_type != ClaimType.deadline or not value or value == "rolling":
        return ""
    past = is_past(ParsedDate(value, dt.date.fromisoformat(value), True), now)
    return (" The stated deadline has passed, but that alone does not show applications are closed "
            "(rolling intake, extensions and stale listings are possible).") if past else ""


def verify_claim(claim_type: ClaimType, evidence: list[EvidenceItem], sources: list[SourceObservation],
                 now: dt.datetime) -> ClaimVerdict:
    usable = [e for e in evidence if e.claim_type == claim_type
              and e.observation.retrieval_outcome == RetrievalOutcome.ok]
    items = sorted(
        (_Item(e, normalize(claim_type, e.extracted_value), e.observation.source_type in AUTHORITATIVE,
               is_fresh(claim_type, e.observation.retrieved_at, now)) for e in usable),
        key=lambda i: (not i.auth, -i.obs.retrieved_at.timestamp(), i.obs.id))

    def verdict(status: S, value: str | None, why: str, step: str | None, *, winner=None, losers=(),
                stale=False, review=False, conflict=False) -> ClaimVerdict:
        assessed = []
        for it in items:
            if conflict and it.decisive:
                role = EvidenceRole.conflicting
            elif not it.decisive:
                role = EvidenceRole.ambiguous
            elif winner is not None and (it in winner or compatible(
                    claim_type, winner[0].norm.value or "", it.norm.value or "")):
                role = EvidenceRole.supports  # includes non-authoritative sources that agree
            else:
                role = EvidenceRole.discrepant
            assessed.append(EvidenceAssessment(
                source_observation_id=it.obs.id, extracted_value=it.ev.extracted_value,
                normalized_value=it.norm.value, excerpt=it.ev.excerpt, evidence_locator=it.ev.evidence_locator,
                confidence=it.ev.confidence, is_certain=it.norm.certain, is_authoritative=it.auth,
                is_fresh=it.fresh, role=role))
        return ClaimVerdict(claim_type=claim_type, status=status, normalized_value=value, explanation=why,
                            next_step=step, checked_at=now, stale=stale, needs_review=review, evidence=assessed)

    if not items:
        failed = [s for s in sources if s.retrieval_outcome != RetrievalOutcome.ok]
        why = ("No readable source states this claim." if not failed else
               f"No readable source states this claim, and {len(failed)} source(s) could not be retrieved "
               "(blocked, not found or timed out). That is not evidence that the claim or the opportunity "
               "is invalid.")
        return verdict(S.unavailable, None, why, "Recheck later or open the official page.")

    decisive = [i for i in items if i.decisive]
    auth, other = [i for i in decisive if i.auth], [i for i in decisive if not i.auth]
    review_only = claim_type in REVIEW_NOT_CONFLICT

    def disagree(groups: list[list[_Item]], who: str) -> ClaimVerdict:
        vals = "; ".join(f"'{g[0].ev.extracted_value}' per {_src(g[0])}" for g in groups)
        if review_only:
            return verdict(S.partially_confirmed, None, f"{who} word this differently: {vals}. "
                           "Free-text claims cannot be compared automatically.",
                           "Read the sources and confirm on the official page.", review=True)
        return verdict(S.conflicting, None, f"{who} give different values: {vals}.",
                       "Open the official page and confirm before relying on either value.",
                       review=True, conflict=True)

    if auth:
        groups = _group(claim_type, auth)
        if len(groups) > 1:
            return disagree(groups, "Authoritative sources")
        win = groups[0]
        value = win[0].norm.value
        best = max(win, key=lambda i: i.obs.retrieved_at)
        diff = [i for i in other if not compatible(claim_type, value or "", i.norm.value or "")]
        fresh = any(i.fresh for i in win)
        base = f"{_src(best)} states '{best.ev.extracted_value}' (retrieved {_stamp(best)})."
        if diff:
            base += (f" {len(diff)} non-authoritative source(s) report different values; they are shown "
                     "for comparison and do not override the authoritative source.")
        base += _past_note(claim_type, value, now)
        if not fresh:
            return verdict(S.partially_confirmed, value,
                           base + f" The evidence is older than the {FRESHNESS_DAYS[claim_type]}-day "
                           f"freshness window for {claim_type.value}.", "Recheck before relying on it.",
                           winner=win, stale=True, review=True)
        return verdict(S.confirmed, value, base, "Confirm critical details on the official page before applying.",
                       winner=win)

    if other:
        groups = _group(claim_type, other)
        if len(groups) > 1:
            return disagree(groups, "Non-authoritative sources")
        win = groups[0]
        value = win[0].norm.value
        domains = {i.obs.domain for i in win}
        stale = not any(i.fresh for i in win)
        if len(domains) >= 2:
            why = (f"{len(domains)} non-authoritative sources agree on '{win[0].ev.extracted_value}', but no "
                   "official or employer source states it. Independence between them is not established.")
            status = S.partially_confirmed
        else:
            why = (f"Only one non-authoritative source ({_src(win[0])}) states '{win[0].ev.extracted_value}'.")
            status = S.unverified
        return verdict(status, value, why + _past_note(claim_type, value, now),
                       "Find and open the official page.", winner=win, stale=stale, review=True)

    # Only ambiguous or low-confidence evidence.
    auth_any = [i for i in items if i.auth]
    reasons = "; ".join(sorted({i.norm.reason or "low extraction confidence" for i in items}))
    if auth_any:
        return verdict(S.partially_confirmed, None, f"{_src(auth_any[0])} mentions this, but the value is "
                       f"ambiguous ({reasons}). The original text is preserved.",
                       "Open the official page and read the exact wording.", review=True)
    return verdict(S.unverified, None, f"Only weak or ambiguous evidence exists ({reasons}).",
                   "Find and open the official page.", review=True)


def verify_opportunity(evidence: list[EvidenceItem], sources: list[SourceObservation], now: dt.datetime,
                       claim_types: tuple[ClaimType, ...] | None = None) -> list[ClaimVerdict]:
    wanted = set(claim_types or ()) | {e.claim_type for e in evidence} | (set() if claim_types else set(CORE_CLAIMS))
    return [verify_claim(t, evidence, sources, now) for t in ClaimType if t in wanted]


def derive_opportunity_status(verdicts: list[ClaimVerdict]) -> OpportunityStatus:
    """Only a confirmed application_status claim can set open/closed. A past deadline or a failed
    fetch never closes an opportunity."""
    for v in verdicts:
        if v.claim_type == ClaimType.application_status and v.status == S.confirmed:
            return OpportunityStatus(v.normalized_value) if v.normalized_value in ("open", "closed") \
                else OpportunityStatus.unknown
    return OpportunityStatus.unknown


def summarize(verdicts: list[ClaimVerdict]) -> VerificationSummary:
    counts = {s.value: 0 for s in S}
    for v in verdicts:
        counts[v.status.value] += 1
    n = len(verdicts)
    score = round(100 * sum(SCORE_WEIGHTS.get(v.status, 0.0) for v in verdicts) / n, 1) if n else None
    disc = sum(1 for v in verdicts if any(e.role == EvidenceRole.discrepant for e in v.evidence))
    return VerificationSummary(total=n, counts=counts, score_percent=score, discrepancies=disc, formula=FORMULA)