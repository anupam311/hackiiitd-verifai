/**
 * Mappers from backend payloads (snake_case, see backend/app/schemas, backend/app/report,
 * backend/app/runs and docs/api.md) to the frontend domain model. Unknown or missing fields map
 * to null/empty — never to invented values.
 */
import type {
  Claim,
  ClaimEvidence,
  ClaimStatus,
  ClaimType,
  Opportunity,
  OpportunityCategory,
  RetrievalOutcome,
  Run,
  RunEvent,
  RunState,
  RunStepId,
  Snapshot,
  SourceObservation,
  SourceType,
  VerificationHeadline,
  VerificationReport,
} from "@/types";
import { countClaims, deriveReportStatus } from "./verification";

type Dict = Record<string, unknown>;
const isDict = (v: unknown): v is Dict => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === "string" && v.trim() !== "" ? v : null);
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const pick = (o: Dict, ...keys: string[]): unknown => {
  for (const k of keys) if (k in o && o[k] !== undefined) return o[k];
  return undefined;
};

const CLAIM_STATUSES: ClaimStatus[] = ["confirmed", "partially_confirmed", "conflicting", "unverified", "unavailable"];
const CLAIM_TYPES: ClaimType[] = ["deadline", "application_status", "application_url", "eligibility", "stipend", "location", "duration", "start_date", "organization", "other"];
const CATEGORIES: OpportunityCategory[] = ["internship", "scholarship", "fellowship", "job", "research", "grant", "competition", "other"];
const SOURCE_TYPES: SourceType[] = ["official", "employer", "institution", "aggregator", "community", "other"];
const RUN_STATES: RunState[] = ["queued", "running", "completed", "partial", "failed", "cancelled"];
const STEPS: RunStepId[] = ["request_received", "discovering", "retrieving_sources", "extracting_claims", "comparing_claims", "detecting_conflicts", "building_report", "finished"];
const OUTCOMES: Record<string, RetrievalOutcome> = {
  ok: "ok",
  partial: "partial",
  blocked: "blocked",
  timeout: "timeout",
  not_found: "not_found",
  http_error: "error",
  error: "error",
  unknown: "unknown",
};

function oneOf<T extends string>(v: unknown, allowed: readonly T[], fallback: T): T {
  return typeof v === "string" && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
}

function domainOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

/** Backend extraction confidence is a 0–1 number; the UI shows three buckets. */
function confidenceBucket(v: unknown): ClaimEvidence["extractionConfidence"] {
  if (typeof v !== "number" || Number.isNaN(v)) return null;
  return v < 0.5 ? "low" : v < 0.8 ? "medium" : "high";
}

function mapSource(s: Dict): SourceObservation | null {
  const url = str(s.url);
  if (!url) return null;
  const id = str(pick(s, "id", "source_observation_id", "observation_id")) ?? url;
  const status = pick(s, "http_status", "httpStatus");
  return {
    id,
    url,
    domain: str(s.domain) ?? domainOf(url),
    name: str(s.name) ?? str(s.domain) ?? domainOf(url),
    sourceType: oneOf(pick(s, "source_type", "sourceType"), SOURCE_TYPES, "other"),
    retrievedAt: str(pick(s, "retrieved_at", "retrievedAt")),
    httpStatus: typeof status === "number" ? status : null,
    outcome: OUTCOMES[String(pick(s, "retrieval_outcome", "outcome") ?? "")] ?? "unknown",
    freshness: oneOf(s.freshness, ["fresh", "stale", "unknown"] as const, "unknown"),
    note: str(s.note) ?? undefined,
  };
}

function mapEvidence(raw: unknown, sink?: Map<string, SourceObservation>): ClaimEvidence | null {
  if (!isDict(raw)) return null;
  const url = str(raw.url);
  if (!url) return null;
  // Evidence points at its source by the backend observation id, so it joins with `report.sources`.
  const sourceId = str(pick(raw, "source_observation_id", "sourceId")) ?? url;
  if (sink && !sink.has(sourceId)) {
    const src = mapSource({ ...raw, id: sourceId });
    if (src) sink.set(sourceId, { ...src, outcome: "ok", freshness: raw.is_fresh === false ? "stale" : raw.is_fresh === true ? "fresh" : "unknown" });
  }
  return {
    sourceId,
    extractedValue: str(pick(raw, "extracted_value", "extractedValue")),
    excerpt: str(raw.excerpt),
    locator: str(pick(raw, "evidence_locator", "locator")),
    extractionConfidence: confidenceBucket(raw.confidence),
  };
}

function mapClaim(raw: unknown, opportunityId: string, sink?: Map<string, SourceObservation>): Claim | null {
  if (!isDict(raw)) return null;
  const type = oneOf(pick(raw, "claim_type", "type"), CLAIM_TYPES, "other");
  const evidence = arr(raw.evidence)
    .map((e) => mapEvidence(e, sink))
    .filter((e): e is ClaimEvidence => e !== null);
  return {
    id: str(raw.id) ?? `${opportunityId}:${type}`,
    type,
    originalWording: str(pick(raw, "original_wording", "originalWording")),
    normalizedValue: str(pick(raw, "normalized_value", "normalizedValue")),
    status: oneOf(raw.status, CLAIM_STATUSES, "unverified"),
    explanation: str(raw.explanation) ?? "No explanation was provided.",
    evidence,
    nextStep: str(pick(raw, "next_step", "nextStep")) ?? undefined,
  };
}

export function mapReport(raw: unknown, opportunityId: string): VerificationReport {
  const d = isDict(raw) ? raw : {};
  const sources = new Map<string, SourceObservation>();
  for (const s of arr(d.sources)) {
    const m = isDict(s) ? mapSource(s) : null;
    if (m) sources.set(m.id, m);
  }
  const claims = arr(d.claims)
    .map((c) => mapClaim(c, opportunityId, sources))
    .filter((c): c is Claim => c !== null);
  const limitations: string[] = arr(d.limitations).filter((x): x is string => typeof x === "string");
  const summary = isDict(d.summary) ? d.summary : null;
  if (summary && str(summary.formula)) limitations.push(`Coverage score: ${String(summary.formula)}`);
  const unresolved: string[] = arr(pick(d, "unresolved_questions", "unresolvedQuestions")).filter((x): x is string => typeof x === "string");
  for (const c of arr(d.claims)) {
    if (isDict(c) && c.needs_review === true && str(c.next_step)) unresolved.push(String(c.next_step));
  }
  return {
    opportunityId,
    runId: str(pick(d, "run_id", "runId")),
    generatedAt: str(pick(d, "generated_at", "generatedAt")),
    claims,
    sources: [...sources.values()],
    unresolvedQuestions: unresolved,
    limitations,
  };
}

/** Backend `deadline` is `{raw_text, date, timezone_name, is_certain}`; older/fixture payloads use a string. */
function mapDeadline(v: unknown): { date: string | null; text: string | null } {
  if (isDict(v)) {
    const date = str(v.date);
    return { date: date && /^\d{4}-\d{2}-\d{2}/.test(date) ? date.slice(0, 10) : null, text: str(pick(v, "raw_text", "text")) };
  }
  const s = str(v);
  if (!s) return { date: null, text: null };
  return /^\d{4}-\d{2}-\d{2}/.test(s) ? { date: s.slice(0, 10), text: null } : { date: null, text: s };
}

export function mapOpportunity(raw: unknown): Opportunity | null {
  if (!isDict(raw)) return null;
  // `SavedItem` wraps the opportunity: `{opportunity, saved_at, latest_*}`.
  if (isDict(raw.opportunity) && !("title" in raw)) return mapOpportunity(raw.opportunity);
  const id = str(raw.id);
  const title = str(raw.title);
  if (!id || !title) return null;
  const claims = arr(raw.claims).map((c) => mapClaim(c, id)).filter((c): c is Claim => c !== null);
  const verification: VerificationHeadline | null =
    claims.length > 0
      ? { reportStatus: deriveReportStatus(claims), counts: countClaims(claims), lastCheckedAt: str(pick(raw, "last_checked_at", "lastCheckedAt")) }
      : null;
  const deadline = mapDeadline(raw.deadline);
  return {
    id,
    title,
    organization: str(raw.organization),
    category: oneOf(raw.category, CATEGORIES, "other"),
    location: str(raw.location),
    workMode: oneOf(pick(raw, "work_mode", "workMode"), ["remote", "on_site", "hybrid", "unknown"] as const, "unknown"),
    deadline: deadline.date,
    deadlineText: str(pick(raw, "deadline_text", "deadlineText")) ?? deadline.text,
    applicationState: oneOf(pick(raw, "application_state", "applicationState", "status"), ["open", "closed", "rolling", "unknown"] as const, "unknown"),
    description: str(raw.description) ?? "",
    tags: arr(raw.tags).filter((x): x is string => typeof x === "string"),
    fieldsOfStudy: arr(pick(raw, "fields_of_study", "fieldsOfStudy")).filter((x): x is string => typeof x === "string"),
    educationLevels: arr(pick(raw, "education_levels", "educationLevels")).filter((x): x is Opportunity["educationLevels"][number] => typeof x === "string"),
    eligibility: [],
    eligibilitySummary: str(pick(raw, "eligibility_summary", "eligibilitySummary")),
    canonicalUrl: str(pick(raw, "canonical_url", "canonicalUrl")),
    applicationUrl: str(pick(raw, "application_url", "applicationUrl")),
    stipendText: str(pick(raw, "stipend", "stipendText")),
    durationText: str(pick(raw, "duration", "durationText")),
    postedAt: str(pick(raw, "posted_at", "postedAt")),
    verification,
    isSample: raw.is_demo === true ? true : undefined,
  };
}

export function mapOpportunities(raw: unknown): Opportunity[] {
  return arr(raw).map(mapOpportunity).filter((o): o is Opportunity => o !== null);
}

/** `GET /api/v1/saved` returns a bare array of `{opportunity, saved_at, latest_status, latest_summary, ...}`. */
export function mapSaved(raw: unknown): { items: Opportunity[]; savedAt: Record<string, string> } {
  const list = isDict(raw) ? arr(raw.items) : arr(raw);
  const items: Opportunity[] = [];
  const savedAt: Record<string, string> = {};
  for (const entry of list) {
    const opp = mapOpportunity(entry);
    if (!opp) continue;
    const summary = isDict(entry) && isDict(entry.latest_summary) ? entry.latest_summary : null;
    const rawCounts = summary && isDict(summary.counts) ? summary.counts : null;
    if (rawCounts) {
      const counts = { confirmed: 0, partially_confirmed: 0, conflicting: 0, unverified: 0, unavailable: 0, total: 0 };
      for (const k of CLAIM_STATUSES) counts[k] = typeof rawCounts[k] === "number" ? (rawCounts[k] as number) : 0;
      counts.total = typeof summary?.total === "number" ? (summary.total as number) : CLAIM_STATUSES.reduce((n, k) => n + counts[k], 0);
      if (counts.total > 0) {
        const reportStatus = counts.conflicting > 0 ? "conflicts_detected" : counts.confirmed === counts.total ? "verified_no_conflicts" : counts.confirmed + counts.partially_confirmed > 0 ? "partially_verified" : "verification_incomplete";
        opp.verification = { reportStatus, counts, lastCheckedAt: isDict(entry) ? str(entry.latest_report_at) : null };
      }
    }
    items.push(opp);
    if (isDict(entry) && str(entry.saved_at)) savedAt[opp.id] = String(entry.saved_at);
  }
  return { items, savedAt };
}

/** Backend event type -> the timeline step it belongs to (see docs/api.md "Event types"). */
const EVENT_STEP: Record<string, { step: RunStepId; state: RunEvent["state"] } | undefined> = {
  "run.started": { step: "request_received", state: "completed" },
  "discovery.started": { step: "discovering", state: "started" },
  "recheck.started": { step: "discovering", state: "started" },
  "discovery.retry": { step: "discovering", state: "started" },
  "discovery.completed": { step: "discovering", state: "completed" },
  "normalize.completed": { step: "retrieving_sources", state: "completed" },
  "extract.started": { step: "extracting_claims", state: "started" },
  "extract.completed": { step: "extracting_claims", state: "completed" },
  "extract.failed": { step: "extracting_claims", state: "failed" },
  "recheck.diff": { step: "comparing_claims", state: "completed" },
  "opportunity.ready": { step: "building_report", state: "completed" },
  "run.completed": { step: "finished", state: "completed" },
  "run.partial": { step: "finished", state: "completed" },
  "run.failed": { step: "finished", state: "failed" },
  "run.cancelled": { step: "finished", state: "failed" },
};

export function mapRun(raw: unknown): Run {
  const d = isDict(raw) ? raw : {};
  const events: RunEvent[] = [];
  arr(d.events).forEach((e, i) => {
    if (!isDict(e)) return;
    const known = EVENT_STEP[String(e.type ?? "")];
    const step = known?.step ?? (typeof e.step === "string" && (STEPS as string[]).includes(e.step) ? (e.step as RunStepId) : null);
    if (!step) return; // events such as source.unavailable are reported as run warnings, not timeline steps
    events.push({
      id: str(e.id) ?? (typeof e.seq === "number" ? `evt-${e.seq}` : `evt-${i}`),
      step,
      state: known?.state ?? oneOf(e.state, ["started", "completed", "failed", "skipped"] as const, "started"),
      message: str(e.message) ?? undefined,
      at: str(pick(e, "at", "timestamp")) ?? new Date(0).toISOString(),
    });
  });
  return {
    id: str(d.id) ?? str(d.run_id) ?? "unknown",
    state: oneOf(d.state, RUN_STATES, "running"),
    events,
    warnings: arr(d.warnings).filter((w): w is string => typeof w === "string"),
    opportunities: mapOpportunities(d.opportunities),
  };
}

/** `GET …/history` returns `{opportunity_id, runs: [{run_id, generated_at, status, summary, claims, unavailable_sources, changes_since_previous}]}`. */
export function mapSnapshots(raw: unknown, opportunityId: string): Snapshot[] {
  const list = isDict(raw) ? arr(pick(raw, "runs", "snapshots", "items")) : arr(raw);
  return list
    .map((s): Snapshot | null => {
      if (!isDict(s)) return null;
      const claims = arr(s.claims)
        .map((c) => (isDict(c) ? { type: oneOf(pick(c, "claim_type", "type"), CLAIM_TYPES, "other"), normalizedValue: str(pick(c, "normalized_value", "normalizedValue")), status: oneOf(c.status, CLAIM_STATUSES, "unverified") } : null))
        .filter((c): c is NonNullable<typeof c> => c !== null);
      const runId = str(pick(s, "run_id", "runId")) ?? "unknown";
      return {
        id: str(s.id) ?? `${opportunityId}:${runId}`,
        opportunityId,
        runId,
        capturedAt: str(pick(s, "generated_at", "captured_at", "capturedAt")) ?? new Date(0).toISOString(),
        runState: oneOf(pick(s, "run_state", "runState"), RUN_STATES, "completed"),
        reportStatus: deriveReportStatus(claims),
        claims,
        unavailableSources: arr(pick(s, "unavailable_sources", "unavailableSources"))
          .map((u) => (isDict(u) && str(u.url) ? { url: String(u.url), reason: str(u.reason) ?? "Unavailable" } : null))
          .filter((u): u is NonNullable<typeof u> => u !== null),
      };
    })
    .filter((s): s is Snapshot => s !== null)
    .sort((a, b) => Date.parse(b.capturedAt) - Date.parse(a.capturedAt));
}
