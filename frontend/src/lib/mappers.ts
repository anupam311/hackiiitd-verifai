/**
 * Defensive mappers from backend payloads (snake_case, see backend/app/models.py
 * and docs/api.md) to the frontend domain model. Unknown or missing fields map
 * to null/empty — never to invented values.
 */
import type {
  Claim,
  ClaimEvidence,
  ClaimStatus,
  ClaimType,
  Opportunity,
  OpportunityCategory,
  Run,
  RunEvent,
  RunState,
  RunStepId,
  Snapshot,
  SourceObservation,
  SourceType,
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
const CLAIM_TYPES: ClaimType[] = ["deadline", "application_status", "application_url", "eligibility", "stipend", "location", "duration", "start_date", "organization"];
const CATEGORIES: OpportunityCategory[] = ["internship", "scholarship", "fellowship", "research", "grant", "competition", "other"];
const SOURCE_TYPES: SourceType[] = ["official", "employer", "institution", "aggregator", "community", "other"];
const RUN_STATES: RunState[] = ["queued", "running", "completed", "partial", "failed"];
const STEPS: RunStepId[] = ["request_received", "discovering", "retrieving_sources", "extracting_claims", "comparing_claims", "detecting_conflicts", "building_report", "finished"];

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

export function mapEvidence(raw: unknown): { evidence: ClaimEvidence; source: SourceObservation } | null {
  if (!isDict(raw)) return null;
  const url = str(raw.url);
  if (!url) return null;
  const source: SourceObservation = {
    id: url,
    url,
    domain: domainOf(url),
    name: domainOf(url),
    sourceType: oneOf(pick(raw, "source_type", "sourceType"), SOURCE_TYPES, "other"),
    retrievedAt: str(pick(raw, "retrieved_at", "retrievedAt")),
    httpStatus: typeof raw.http_status === "number" ? raw.http_status : null,
    outcome: "ok",
    freshness: "unknown",
  };
  const evidence: ClaimEvidence = {
    sourceId: url,
    extractedValue: str(pick(raw, "extracted_value", "extractedValue")),
    excerpt: str(raw.excerpt),
    locator: str(pick(raw, "evidence_locator", "locator")),
    extractionConfidence: null,
  };
  return { evidence, source };
}

export function mapClaim(raw: unknown, opportunityId: string, sinkSources?: Map<string, SourceObservation>): Claim | null {
  if (!isDict(raw)) return null;
  const type = oneOf(pick(raw, "claim_type", "type"), CLAIM_TYPES, "organization");
  const evidence: ClaimEvidence[] = [];
  for (const e of arr(raw.evidence)) {
    const m = mapEvidence(e);
    if (!m) continue;
    evidence.push(m.evidence);
    sinkSources?.set(m.source.id, m.source);
  }
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
    if (isDict(s) && str(s.url)) {
      const url = String(s.url);
      sources.set(String(s.id ?? url), {
        id: String(s.id ?? url),
        url,
        domain: domainOf(url),
        name: str(s.name) ?? domainOf(url),
        sourceType: oneOf(pick(s, "source_type", "sourceType"), SOURCE_TYPES, "other"),
        retrievedAt: str(pick(s, "retrieved_at", "retrievedAt")),
        httpStatus: typeof pick(s, "http_status", "httpStatus") === "number" ? (pick(s, "http_status", "httpStatus") as number) : null,
        outcome: oneOf(s.outcome, ["ok", "partial", "blocked", "timeout", "not_found", "error"] as const, "ok"),
        freshness: oneOf(s.freshness, ["fresh", "stale", "unknown"] as const, "unknown"),
        note: str(s.note) ?? undefined,
      });
    }
  }
  const claims = arr(d.claims).map((c) => mapClaim(c, opportunityId, sources)).filter((c): c is Claim => c !== null);
  return {
    opportunityId,
    runId: str(pick(d, "run_id", "runId")),
    generatedAt: str(pick(d, "generated_at", "generatedAt")),
    claims,
    sources: [...sources.values()],
    unresolvedQuestions: arr(pick(d, "unresolved_questions", "unresolvedQuestions")).filter((x): x is string => typeof x === "string"),
    limitations: arr(d.limitations).filter((x): x is string => typeof x === "string"),
  };
}

export function mapOpportunity(raw: unknown): Opportunity | null {
  if (!isDict(raw)) return null;
  const id = str(raw.id);
  const title = str(raw.title);
  if (!id || !title) return null;
  const claims = arr(raw.claims).map((c) => mapClaim(c, id)).filter((c): c is Claim => c !== null);
  const verification =
    claims.length > 0
      ? { reportStatus: deriveReportStatus(claims), counts: countClaims(claims), lastCheckedAt: str(pick(raw, "last_checked_at", "lastCheckedAt")) }
      : null;
  const deadline = str(raw.deadline);
  return {
    id,
    title,
    organization: str(raw.organization),
    category: oneOf(raw.category, CATEGORIES, "other"),
    location: str(raw.location),
    workMode: oneOf(pick(raw, "work_mode", "workMode"), ["remote", "on_site", "hybrid", "unknown"] as const, "unknown"),
    deadline: deadline && /^\d{4}-\d{2}-\d{2}/.test(deadline) ? deadline.slice(0, 10) : null,
    deadlineText: str(pick(raw, "deadline_text", "deadlineText")) ?? (deadline && !/^\d{4}-\d{2}-\d{2}/.test(deadline) ? deadline : null),
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
  };
}

export function mapOpportunities(raw: unknown): Opportunity[] {
  return arr(raw).map(mapOpportunity).filter((o): o is Opportunity => o !== null);
}

export function mapRun(raw: unknown): Run {
  const d = isDict(raw) ? raw : {};
  const events: RunEvent[] = arr(d.events)
    .map((e, i): RunEvent | null => {
      if (!isDict(e)) return null;
      return {
        id: str(e.id) ?? `evt-${i}`,
        step: oneOf(e.step, STEPS, "request_received"),
        state: oneOf(e.state, ["started", "completed", "failed", "skipped"] as const, "started"),
        message: str(e.message) ?? undefined,
        at: str(pick(e, "at", "timestamp")) ?? new Date(0).toISOString(),
      };
    })
    .filter((e): e is RunEvent => e !== null);
  return {
    id: str(d.id) ?? str(pick(d, "run_id")) ?? "unknown",
    state: oneOf(d.state, RUN_STATES, "running"),
    events,
    warnings: arr(d.warnings).filter((w): w is string => typeof w === "string"),
  };
}

export function mapSnapshots(raw: unknown, opportunityId: string): Snapshot[] {
  const list = isDict(raw) ? arr(pick(raw, "snapshots", "items")) : arr(raw);
  return list
    .map((s): Snapshot | null => {
      if (!isDict(s)) return null;
      const claims = arr(s.claims)
        .map((c) => (isDict(c) ? { type: oneOf(pick(c, "claim_type", "type"), CLAIM_TYPES, "organization"), normalizedValue: str(pick(c, "normalized_value", "normalizedValue")), status: oneOf(c.status, CLAIM_STATUSES, "unverified") } : null))
        .filter((c): c is NonNullable<typeof c> => c !== null);
      return {
        id: str(s.id) ?? `${opportunityId}:${str(pick(s, "run_id", "runId")) ?? "run"}`,
        opportunityId,
        runId: str(pick(s, "run_id", "runId")) ?? "unknown",
        capturedAt: str(pick(s, "captured_at", "capturedAt")) ?? new Date(0).toISOString(),
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
