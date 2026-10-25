/**
 * Domain model for VERIFAI.
 *
 * Mirrors docs/architecture.md and docs/verification_policy.md. Claim statuses
 * match the backend `VerificationStatus` literal in backend/app/models.py.
 */

export type ClaimStatus =
  | "confirmed"
  | "partially_confirmed"
  | "conflicting"
  | "unverified"
  | "unavailable";

export type ClaimType =
  | "deadline"
  | "application_status"
  | "application_url"
  | "eligibility"
  | "stipend"
  | "location"
  | "duration"
  | "start_date"
  | "organization"
  | "other";

/** Claims that must be checked before a report may be called "verified". */
export const CORE_CLAIM_TYPES: readonly ClaimType[] = [
  "deadline",
  "application_status",
  "application_url",
  "eligibility",
] as const;

export type OpportunityCategory =
  | "internship"
  | "scholarship"
  | "fellowship"
  | "job"
  | "research"
  | "grant"
  | "competition"
  | "other";

export type WorkMode = "remote" | "on_site" | "hybrid" | "unknown";

export type EducationLevel =
  | "high_school"
  | "undergraduate"
  | "postgraduate"
  | "doctoral"
  | "any"
  | "unknown";

/** Open/closed state as *reported by a source*. Never inferred from failures. */
export type ApplicationState = "open" | "closed" | "rolling" | "unknown";

export type SourceType =
  | "official"
  | "employer"
  | "institution"
  | "aggregator"
  | "community"
  | "other";

export type SourceFreshness = "fresh" | "stale" | "unknown";

export type RetrievalOutcome = "ok" | "partial" | "blocked" | "timeout" | "not_found" | "error" | "unknown";

export interface EligibilityRequirement {
  id: string;
  kind: "education_level" | "field_of_study" | "location" | "graduation_year" | "skill" | "other";
  /** Human-readable requirement as written by the source. */
  text: string;
  /** Normalised structured values when the extractor could produce them. */
  values?: string[];
  /** Used by graduation_year requirements. */
  minYear?: number;
  maxYear?: number;
  sourceUrl?: string;
}

export interface Opportunity {
  id: string;
  title: string;
  organization: string | null;
  category: OpportunityCategory;
  location: string | null;
  workMode: WorkMode;
  /** ISO date (YYYY-MM-DD) or null when no deadline is known. */
  deadline: string | null;
  /** Original deadline wording, preserved per verification policy. */
  deadlineText?: string | null;
  applicationState: ApplicationState;
  description: string;
  tags: string[];
  fieldsOfStudy: string[];
  educationLevels: EducationLevel[];
  eligibility: EligibilityRequirement[];
  eligibilitySummary?: string | null;
  canonicalUrl: string | null;
  applicationUrl: string | null;
  stipendText?: string | null;
  durationText?: string | null;
  startDateText?: string | null;
  postedAt?: string | null;
  /** Application instructions extracted from the source, used to build checklists. */
  applicationSteps?: ApplicationStep[];
  /** Latest report headline for list views; the full report is fetched separately. */
  verification: VerificationHeadline | null;
  /** True for records that come from the development fixture module. */
  isSample?: boolean;
}

export interface ApplicationStep {
  id: string;
  group: "documents" | "links" | "form" | "submission";
  label: string;
  detail?: string;
  sourceUrl?: string | null;
  sourceLabel?: string | null;
}

export interface VerificationHeadline {
  reportStatus: ReportStatus;
  counts: ClaimCounts;
  lastCheckedAt: string | null;
}

export interface ClaimCounts {
  confirmed: number;
  partially_confirmed: number;
  conflicting: number;
  unverified: number;
  unavailable: number;
  total: number;
}

export type ReportStatus =
  | "verified_no_conflicts"
  | "conflicts_detected"
  | "partially_verified"
  | "verification_incomplete";

export interface SourceObservation {
  id: string;
  url: string;
  domain: string;
  /** Display name, e.g. "Helio careers page". */
  name: string;
  sourceType: SourceType;
  retrievedAt: string | null;
  httpStatus?: number | null;
  outcome: RetrievalOutcome;
  freshness: SourceFreshness;
  /** Extra explanation for failures; a failure is never proof of closure. */
  note?: string;
}

export interface ClaimEvidence {
  sourceId: string;
  /** Value as extracted from the source (original wording). */
  extractedValue: string | null;
  /** Verbatim excerpt or locator. Never synthesised by the UI. */
  excerpt: string | null;
  locator?: string | null;
  extractionConfidence?: "low" | "medium" | "high" | null;
}

export interface Claim {
  id: string;
  type: ClaimType;
  /** Wording of the claim as first discovered/extracted. */
  originalWording: string | null;
  normalizedValue: string | null;
  status: ClaimStatus;
  explanation: string;
  evidence: ClaimEvidence[];
  nextStep?: string;
}

export interface VerificationReport {
  opportunityId: string;
  runId: string | null;
  generatedAt: string | null;
  claims: Claim[];
  sources: SourceObservation[];
  unresolvedQuestions: string[];
  limitations: string[];
  isSample?: boolean;
}

export interface SourceComparisonRow {
  claimType: ClaimType;
  /** Value found per source id; null means the source did not state it. */
  values: Record<string, string | null>;
  agreement: "agree" | "partial" | "conflict" | "single_source" | "missing";
  summary: string;
}

export interface SourceComparison {
  opportunityId: string;
  sources: SourceObservation[];
  rows: SourceComparisonRow[];
  isSample?: boolean;
}

/* ───────────── Runs ───────────── */

export type RunState = "queued" | "running" | "completed" | "partial" | "failed" | "cancelled";

export type RunStepId =
  | "request_received"
  | "discovering"
  | "retrieving_sources"
  | "extracting_claims"
  | "comparing_claims"
  | "detecting_conflicts"
  | "building_report"
  | "finished";

export interface RunEvent {
  id: string;
  step: RunStepId;
  state: "started" | "completed" | "failed" | "skipped";
  message?: string;
  at: string;
}

export interface Run {
  id: string;
  state: RunState;
  events: RunEvent[];
  warnings: string[];
  /** Opportunities the run has finished so far (partial results appear here while it runs). */
  opportunities?: Opportunity[];
  isSample?: boolean;
}

/* ───────────── History ───────────── */

export type ChangeKind = "unchanged" | "changed" | "incomplete" | "source_unavailable" | "new_conflict";

export interface SnapshotClaim {
  type: ClaimType;
  normalizedValue: string | null;
  status: ClaimStatus;
}

export interface Snapshot {
  id: string;
  opportunityId: string;
  runId: string;
  capturedAt: string;
  runState: RunState;
  reportStatus: ReportStatus;
  claims: SnapshotClaim[];
  unavailableSources: { url: string; reason: string }[];
}

export interface ClaimChange {
  claimType: ClaimType;
  kind: ChangeKind;
  before: SnapshotClaim | null;
  after: SnapshotClaim | null;
  note: string;
}

/* ───────────── Profile & matching ───────────── */

export interface ApplicantProfile {
  educationLevel: EducationLevel;
  degree: string;
  fieldOfStudy: string;
  institution: string;
  graduationYear: number | null;
  location: string;
  preferredRegions: string[];
  experience: string;
  skills: string[];
  researchInterests: string[];
  preferredCategories: OpportunityCategory[];
  workModePreference: WorkMode | "any";
}

export type MatchOutcome = "match" | "mismatch" | "unknown";

export interface MatchReason {
  requirementId: string;
  requirement: string;
  outcome: MatchOutcome;
  reasoning: string;
}

export type FitLevel = "strong" | "partial" | "weak" | "insufficient";

export interface EligibilityAnalysis {
  reasons: MatchReason[];
  fit: FitLevel;
  counts: { match: number; mismatch: number; unknown: number };
  /** True when the profile has too little information to evaluate anything. */
  profileIncomplete: boolean;
}

/* ───────────── Checklist ───────────── */

export interface ChecklistItem {
  id: string;
  group: "eligibility" | "documents" | "links" | "form" | "deadline" | "submission";
  label: string;
  detail?: string;
  sourceUrl?: string | null;
  sourceLabel?: string | null;
  done: boolean;
}

/* ───────────── Notifications ───────────── */

export type NotificationKind =
  | "recheck_result"
  | "deadline_changed"
  | "conflict_detected"
  | "saved_update"
  | "verification_failed";

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  opportunityId?: string;
  createdAt: string;
  read: boolean;
  isSample?: boolean;
}

/* ───────────── Session ───────────── */

export interface SessionUser {
  id: string;
  email: string | null;
  displayName: string;
  avatarUrl?: string | null;
  providers?: Array<"google" | "github">;
}
