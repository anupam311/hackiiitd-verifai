"""Discovery pipeline: provider -> normalize -> extract -> group -> verify -> report -> store.
Every step reports through RunContext so the UI shows what actually happened."""
import datetime as dt
import hashlib
from dataclasses import dataclass
from typing import Callable

from app.ai.client import LLMClient
from app.ai.errors import LLMAuthError, LLMError, LLMNotConfigured
from app.ai.extraction import extract_from_text, sanitize
from app.ai.models import ExtractionResult
from app.discovery.base import DiscoveryProvider, RawSourceRecord
from app.discovery.normalize import normalize_records
from app.discovery.retry import RetryPolicy, discover_with_policy
from app.report.builder import build_report
from app.repositories.base import Store
from app.runs.manager import RunContext
from app.schemas.common import utc_now
from app.schemas.discovery import DiscoverySearchRequest
from app.schemas.enums import (ClaimType, OpportunityCategory, RetrievalOutcome, RunState, SourceType,
                               VerificationStatus)
from app.schemas.opportunity import DeadlineInfo, Opportunity
from app.schemas.source import SourceObservation
from app.verification.dates import parse_date_text
from app.verification.models import EvidenceItem, EvidenceRole
from app.verification.normalizers import norm_text
from app.verification.policy import AUTHORITATIVE, verify_opportunity


@dataclass
class PipelineDeps:
    provider: DiscoveryProvider
    llm: LLMClient
    store: Store
    retry: RetryPolicy = RetryPolicy()
    extract_retry: RetryPolicy = RetryPolicy(max_attempts=3, timeout_s=60.0)
    clock: Callable[[], dt.datetime] = utc_now


@dataclass
class Ingested:
    obs: SourceObservation
    extraction: ExtractionResult | None


async def ingest(ctx: RunContext, records: list[RawSourceRecord], deps: PipelineDeps,
                 now: dt.datetime) -> tuple[list[Ingested], bool]:
    """Normalize records and extract facts from each readable page. Returns (sources, partial)."""
    norm = normalize_records(records, now=now)
    ctx.emit("normalize.completed", "Sources normalized.", observations=len(norm.observations),
             rejected=len(norm.rejected), duplicates=norm.duplicates_dropped)
    partial = bool(norm.rejected)
    if norm.rejected:
        ctx.warn(f"{len(norm.rejected)} source record(s) were rejected as invalid.")
    out: list[Ingested] = []
    for obs in norm.observations:
        text = norm.content_by_observation.get(obs.id)
        if obs.retrieval_outcome != RetrievalOutcome.ok:
            ctx.emit("source.unavailable", "A source could not be retrieved.", domain=obs.domain,
                     outcome=obs.retrieval_outcome.value)
            ctx.warn(f"{obs.domain} could not be retrieved ({obs.retrieval_outcome.value}); "
                     "this does not show the opportunity is closed.")
            out.append(Ingested(obs, None))
        elif not text:
            ctx.emit("source.no_content", "A source returned no readable text.", domain=obs.domain)
            out.append(Ingested(obs, None))
        else:
            ctx.emit("extract.started", "Extracting claims.", domain=obs.domain)
            try:
                res = await extract_from_text(deps.llm, text, source_observation_id=obs.id,
                                              policy=deps.extract_retry)
            except (LLMAuthError, LLMNotConfigured):
                raise  # a configuration problem affects every source: fail the run
            except LLMError as exc:
                partial = True
                ctx.emit("extract.failed", "Extraction failed for a source.", domain=obs.domain, code=exc.code)
                ctx.warn(f"Could not extract claims from {obs.domain} ({exc.code}).")
                out.append(Ingested(obs, None))
                continue
            ctx.emit("extract.completed", "Claims extracted.", domain=obs.domain, facts=len(res.facts),
                     dropped=len(res.dropped))
            out.append(Ingested(obs, res))
    return out, partial


def _org(ing: Ingested) -> str | None:
    facts = [f for f in (ing.extraction.facts if ing.extraction else []) if f.claim_type == ClaimType.organization]
    return max(facts, key=lambda f: f.confidence).extracted_value if facts else None


def _rank(ing: Ingested) -> tuple:
    return (ing.obs.source_type not in AUTHORITATIVE, -ing.obs.retrieved_at.timestamp(), ing.obs.id)


def _deadline_info(verdicts) -> DeadlineInfo | None:
    v = next((v for v in verdicts if v.claim_type == ClaimType.deadline), None)
    if not v or not v.evidence:
        return None
    e = next((e for e in v.evidence if e.role == EvidenceRole.supports), v.evidence[0])
    p = parse_date_text(e.extracted_value)
    return DeadlineInfo(raw_text=e.extracted_value[:200], date=p.date, timezone_name=p.timezone_name,
                        is_certain=p.is_certain and v.status == VerificationStatus.confirmed)


def evidence_for(ings: list[Ingested]) -> list[EvidenceItem]:
    return [EvidenceItem(claim_type=f.claim_type, extracted_value=f.extracted_value, excerpt=f.excerpt,
                         evidence_locator=f.evidence_locator, confidence=f.confidence, observation=i.obs,
                         extraction_method=f.extraction_method, schema_version=f.schema_version)
            for i in ings if i.extraction for f in i.extraction.facts]


async def run_discovery(ctx: RunContext, request: DiscoverySearchRequest, deps: PipelineDeps) -> RunState:
    now = deps.clock()
    ctx.emit("discovery.started", "Searching live sources.")

    def on_retry(attempt: int, code: str, delay: float) -> None:
        ctx.emit("discovery.retry", f"Transient provider error; retrying in {delay:g}s.",
                 attempt=attempt, code=code, delay_s=delay)

    result = await discover_with_policy(deps.provider, request, deps.retry, on_retry=on_retry)
    ctx.emit("discovery.completed", "Provider returned results.", records=len(result.records),
             complete=result.complete)
    for w in result.warnings:
        ctx.warn(sanitize(w, 200))  # provider text is untrusted
    if not result.records:
        ctx.warn("No sources were found.")

    ingested, partial = await ingest(ctx, result.records, deps, now)
    groups: dict[str, list[Ingested]] = {}
    unattributed = 0
    for ing in ingested:
        title = ing.extraction.opportunity_title if ing.extraction else None
        org = _org(ing)
        if ing.extraction and title and org:
            groups.setdefault(norm_text(title) + "|" + norm_text(org), []).append(ing)
        elif ing.extraction:
            unattributed += 1
    if unattributed:
        ctx.warn(f"{unattributed} source(s) did not state a title and organization and were not attributed.")

    for key, ings in groups.items():
        ings.sort(key=_rank)
        primary = ings[0]
        opp_id = "opp_" + hashlib.sha256(key.encode()).hexdigest()[:12]
        verdicts = verify_opportunity(evidence_for(ings), [i.obs for i in ings], now)
        report = build_report(opp_id, ctx.run_id, verdicts, [i.obs for i in ings], now)
        existing = deps.store.get_opportunity(opp_id)
        loc = next((f.extracted_value for i in ings if i.extraction for f in i.extraction.facts
                    if f.claim_type == ClaimType.location), None)
        opp = Opportunity(
            id=opp_id, title=primary.extraction.opportunity_title, organization=_org(primary),
            category=next((i.extraction.opportunity_category for i in ings
                           if i.extraction.opportunity_category), OpportunityCategory.other),
            location=loc, canonical_url=primary.obs.url, deadline=_deadline_info(verdicts),
            status=report.status, created_at=existing.created_at if existing else now, updated_at=now)
        deps.store.save_opportunity(opp)
        deps.store.save_report(report)
        ctx.add_opportunity(opp)
        ctx.emit("opportunity.ready", "An opportunity report is ready.", opportunity_id=opp.id)

    return RunState.partial if (partial or not result.complete) else RunState.completed


async def run_recheck(ctx: RunContext, opportunity_id: str, deps: PipelineDeps) -> RunState:
    """Re-fetch the sources of the latest report, verify again, store a new snapshot and diff it."""
    from app.discovery.retry import fetch_with_policy
    from app.report.diff import diff_reports

    now = deps.clock()
    opp, prev = deps.store.get_opportunity(opportunity_id), deps.store.get_latest_report(opportunity_id)
    if opp is None or prev is None:
        raise LookupError("nothing to recheck")
    urls = [s.url for s in prev.sources]
    ctx.emit("recheck.started", "Re-fetching known sources.", sources=len(urls))

    def on_retry(attempt: int, code: str, delay: float) -> None:
        ctx.emit("discovery.retry", f"Transient provider error; retrying in {delay:g}s.",
                 attempt=attempt, code=code, delay_s=delay)

    result = await fetch_with_policy(deps.provider, urls, deps.retry, on_retry=on_retry)
    ctx.emit("discovery.completed", "Provider returned results.", records=len(result.records),
             complete=result.complete)
    for w in result.warnings:
        ctx.warn(sanitize(w, 200))

    ingested, partial = await ingest(ctx, result.records, deps, now)
    returned = {i.obs.url for i in ingested}
    missing = [u for u in urls if u not in returned]
    if missing:
        ctx.warn(f"{len(missing)} previously known source(s) returned no result.")
    sources = [i.obs for i in ingested]
    verdicts = verify_opportunity(evidence_for(ingested), sources, now)
    report = build_report(opportunity_id, ctx.run_id, verdicts, sources, now)
    diff = diff_reports(prev, report)

    updated = opp.model_copy(update={"status": report.status, "updated_at": now,
                                     "deadline": _deadline_info(verdicts) or opp.deadline})
    deps.store.save_opportunity(updated)
    deps.store.save_report(report)
    ctx.add_opportunity(updated)
    kinds = [c.change for c in diff.changes]
    ctx.emit("recheck.diff", "Compared with the previous snapshot.", changed=kinds.count("changed"),
             appeared=kinds.count("appeared"), disappeared=kinds.count("disappeared"),
             became_stale=kinds.count("became_stale"), unchanged=diff.unchanged)
    ctx.emit("opportunity.ready", "An opportunity report is ready.", opportunity_id=opportunity_id)
    return RunState.partial if (partial or not result.complete) else RunState.completed