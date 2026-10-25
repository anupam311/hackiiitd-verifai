import type { ClaimStatus, ClaimType, OpportunityCategory, ReportStatus, SourceType, WorkMode, EducationLevel, RunState } from "@/types";

export const CLAIM_STATUS_LABEL: Record<ClaimStatus, string> = {
  confirmed: "Confirmed",
  partially_confirmed: "Partially confirmed",
  conflicting: "Conflicting",
  unverified: "Unverified",
  unavailable: "Unavailable",
};

export const CLAIM_STATUS_HELP: Record<ClaimStatus, string> = {
  confirmed: "Evidence from an authoritative or sufficiently corroborated source supports this claim.",
  partially_confirmed: "Part of the claim is supported, but some detail remains ambiguous.",
  conflicting: "Sources disagree materially. Both values stay visible.",
  unverified: "There is not enough evidence to support or refute this claim.",
  unavailable: "The claim could not be evaluated because source content was missing or inaccessible.",
};

export const CLAIM_TYPE_LABEL: Record<ClaimType, string> = {
  deadline: "Deadline",
  application_status: "Application status",
  application_url: "Application link",
  eligibility: "Eligibility",
  stipend: "Stipend / funding",
  location: "Location",
  duration: "Duration",
  start_date: "Start date",
  organization: "Organisation",
  other: "Other detail",
};

export const REPORT_STATUS_LABEL: Record<ReportStatus, string> = {
  verified_no_conflicts: "Verified — no conflicts detected",
  conflicts_detected: "Conflicts detected",
  partially_verified: "Partially verified",
  verification_incomplete: "Verification incomplete",
};

export const REPORT_STATUS_SHORT: Record<ReportStatus, string> = {
  verified_no_conflicts: "No conflicts detected",
  conflicts_detected: "Conflicts detected",
  partially_verified: "Partially verified",
  verification_incomplete: "Incomplete",
};

export const CATEGORY_LABEL: Record<OpportunityCategory, string> = {
  internship: "Internship",
  scholarship: "Scholarship",
  fellowship: "Fellowship",
  job: "Job",
  research: "Research programme",
  grant: "Grant",
  competition: "Competition",
  other: "Other",
};

export const WORK_MODE_LABEL: Record<WorkMode, string> = {
  remote: "Remote",
  on_site: "On-site",
  hybrid: "Hybrid",
  unknown: "Work mode unknown",
};

export const EDUCATION_LABEL: Record<EducationLevel, string> = {
  high_school: "High school",
  undergraduate: "Undergraduate",
  postgraduate: "Postgraduate",
  doctoral: "Doctoral",
  any: "Any level",
  unknown: "Not specified",
};

export const SOURCE_TYPE_LABEL: Record<SourceType, string> = {
  official: "Official",
  employer: "Employer",
  institution: "Institution",
  aggregator: "Aggregator",
  community: "Community",
  other: "Other",
};

export const RUN_STATE_LABEL: Record<RunState, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  partial: "Partially completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

export function titleCase(s: string): string {
  return s.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function pluralize(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Stable colour index for an organisation avatar. */
export function hueFor(name: string | null | undefined): number {
  let h = 0;
  for (const ch of name ?? "") h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}
