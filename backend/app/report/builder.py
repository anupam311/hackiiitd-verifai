"""Assemble stored reports and derive the side-by-side source comparison. Pure functions, no I/O."""
import datetime as dt

from app.report.models import (ClaimReport, ComparisonCell, ComparisonRow, ConflictCallout, ConflictValue,
                               EvidenceEntry, SourceComparison, SourceSummary, VerificationReport)
from app.schemas.enums import RetrievalOutcome, SourceType, VerificationStatus
from app.schemas.source import SourceObservation
from app.verification.models import ClaimVerdict, EvidenceRole
from app.verification.policy import AUTHORITATIVE, derive_opportunity_status, summarize

_RANK = {SourceType.official: 0, SourceType.employer: 1, SourceType.institution: 2,
         SourceType.aggregator: 3, SourceType.community: 4, SourceType.other: 5}


def _ordered(sources: list[SourceObservation]) -> list[SourceObservation]:
    return sorted(sources, key=lambda s: (_RANK[s.source_type], -s.retrieved_at.timestamp(), s.id))


def build_report(opportunity_id: str, run_id: str, verdicts: list[ClaimVerdict],
                 observations: list[SourceObservation], now: dt.datetime) -> VerificationReport:
    by_id = {o.id: o for o in observations}
    claims = []
    for v in verdicts:
        entries = []
        for a in v.evidence:
            o = by_id.get(a.source_observation_id)
            if o is None:
                raise ValueError("evidence references an unknown source observation")
            entries.append(EvidenceEntry(
                source_observation_id=o.id, url=o.url, domain=o.domain, source_type=o.source_type,
                retrieved_at=o.retrieved_at, extracted_value=a.extracted_value, normalized_value=a.normalized_value,
                excerpt=a.excerpt, evidence_locator=a.evidence_locator, confidence=a.confidence,
                is_authoritative=a.is_authoritative, is_fresh=a.is_fresh, role=a.role))
        claims.append(ClaimReport(
            claim_type=v.claim_type, status=v.status, normalized_value=v.normalized_value,
            explanation=v.explanation, next_step=v.next_step, checked_at=v.checked_at, stale=v.stale,
            needs_review=v.needs_review, evidence=entries))
    return VerificationReport(
        run_id=run_id, opportunity_id=opportunity_id, generated_at=now,
        status=derive_opportunity_status(verdicts), summary=summarize(verdicts), claims=claims,
        sources=_ordered(observations))


def _cell_state(source: SourceObservation, entries: list[EvidenceEntry]) -> ComparisonCell:
    if source.retrieval_outcome != RetrievalOutcome.ok:
        return ComparisonCell(source_observation_id=source.id, value=None, state="unavailable")
    mine = [e for e in entries if e.source_observation_id == source.id]
    if not mine:
        return ComparisonCell(source_observation_id=source.id, value=None, state="missing")
    roles = {e.role for e in mine}
    if roles & {EvidenceRole.discrepant, EvidenceRole.conflicting}:
        state = "differs"
    elif EvidenceRole.ambiguous in roles:
        state = "ambiguous"
    else:
        state = "agrees"
    return ComparisonCell(source_observation_id=source.id, value=mine[0].extracted_value, state=state)


def build_comparison(report: VerificationReport) -> SourceComparison:
    sources = report.sources
    rows, conflicts, warnings = [], [], []
    for c in report.claims:
        cells = [_cell_state(s, c.evidence) for s in sources]
        states = {x.state for x in cells}
        agreement = ("conflict" if "differs" in states else "partial" if "ambiguous" in states
                     else "agree" if "agrees" in states else "missing")
        rows.append(ComparisonRow(claim_type=c.claim_type, status=c.status, agreement=agreement, cells=cells))
        if agreement == "conflict":
            vals = [ConflictValue(source_observation_id=e.source_observation_id, url=e.url, domain=e.domain,
                                  source_type=e.source_type, retrieved_at=e.retrieved_at,
                                  extracted_value=e.extracted_value)
                    for e in c.evidence if e.role != EvidenceRole.ambiguous]
            if c.status == VerificationStatus.conflicting:
                msg = f"Credible sources disagree about {c.claim_type.value}. Review each source below."
            else:
                msg = (f"An authoritative source and other sources give different values for "
                       f"{c.claim_type.value}. The authoritative source is used, but verify on the official page.")
            conflicts.append(ConflictCallout(claim_type=c.claim_type, status=c.status, message=msg, values=vals))
        for e in c.evidence:
            if not e.is_fresh and e.role in (EvidenceRole.supports, EvidenceRole.conflicting):
                warnings.append(f"Evidence for {c.claim_type.value} from {e.domain} is stale "
                                f"(retrieved {e.retrieved_at:%Y-%m-%d %H:%MZ}). Recheck before relying on it.")
    for s in sources:
        if s.retrieval_outcome != RetrievalOutcome.ok:
            warnings.append(f"{s.domain} could not be retrieved ({s.retrieval_outcome.value}). "
                            "This does not show the opportunity is closed.")
    return SourceComparison(
        opportunity_id=report.opportunity_id, run_id=report.run_id, generated_at=report.generated_at,
        sources=[SourceSummary(observation_id=s.id, url=s.url, domain=s.domain, source_type=s.source_type,
                               retrieved_at=s.retrieved_at, retrieval_outcome=s.retrieval_outcome,
                               is_authoritative=s.source_type in AUTHORITATIVE) for s in sources],
        rows=rows, conflicts=conflicts, warnings=list(dict.fromkeys(warnings)))