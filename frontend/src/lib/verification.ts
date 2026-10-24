import type { Claim, ClaimCounts, ClaimStatus, ClaimType, ReportStatus, VerificationReport } from "@/types";
import { CORE_CLAIM_TYPES } from "@/types";

export function countClaims(claims: Pick<Claim, "status">[]): ClaimCounts {
  const counts: ClaimCounts = { confirmed: 0, partially_confirmed: 0, conflicting: 0, unverified: 0, unavailable: 0, total: claims.length };
  for (const c of claims) counts[c.status] += 1;
  return counts;
}

/**
 * Report-level status. Deliberately conservative:
 *  - any conflict wins;
 *  - "verified" requires every core claim to exist AND be confirmed;
 *  - otherwise some support => partially verified; none => incomplete.
 */
export function deriveReportStatus(claims: Pick<Claim, "type" | "status">[]): ReportStatus {
  if (claims.length === 0) return "verification_incomplete";
  if (claims.some((c) => c.status === "conflicting")) return "conflicts_detected";
  const byType = new Map<ClaimType, ClaimStatus>(claims.map((c) => [c.type, c.status]));
  const coreConfirmed = CORE_CLAIM_TYPES.every((t) => byType.get(t) === "confirmed");
  const allConfirmed = claims.every((c) => c.status === "confirmed");
  if (coreConfirmed && allConfirmed) return "verified_no_conflicts";
  const supported = claims.some((c) => c.status === "confirmed" || c.status === "partially_confirmed");
  return supported ? "partially_verified" : "verification_incomplete";
}

export interface CoverageScore {
  /** 0–100 */
  percent: number;
  points: number;
  total: number;
  formula: string;
  caveat: string;
}

/**
 * Transparent evidence coverage score (docs/verification_policy.md "Score guidance").
 * confirmed = 1 point, partially confirmed = 0.5, everything else = 0.
 * It measures how much of the claim set is supported — NOT the probability that
 * an opportunity is authentic.
 */
export function coverageScore(counts: ClaimCounts): CoverageScore | null {
  if (counts.total === 0) return null;
  const points = counts.confirmed + 0.5 * counts.partially_confirmed;
  return {
    percent: Math.round((points / counts.total) * 100),
    points,
    total: counts.total,
    formula: `(${counts.confirmed} confirmed + 0.5 × ${counts.partially_confirmed} partially confirmed) ÷ ${counts.total} claims = ${points} ÷ ${counts.total}`,
    caveat:
      "Measures how many claims have supporting evidence. It is not a probability that the opportunity is authentic, and conflicts, unverified and unavailable claims count as zero.",
  };
}

/** Core claims that are absent from a report, i.e. never checked. */
export function missingCoreClaims(claims: Pick<Claim, "type">[]): ClaimType[] {
  const present = new Set(claims.map((c) => c.type));
  return CORE_CLAIM_TYPES.filter((t) => !present.has(t));
}

export function reportTone(status: ReportStatus): "green" | "amber" | "red" | "gray" {
  switch (status) {
    case "verified_no_conflicts":
      return "green";
    case "conflicts_detected":
      return "red";
    case "partially_verified":
      return "amber";
    default:
      return "gray";
  }
}

export function claimTone(status: ClaimStatus): "green" | "amber" | "red" | "gray" {
  switch (status) {
    case "confirmed":
      return "green";
    case "partially_confirmed":
      return "amber";
    case "conflicting":
      return "red";
    default:
      return "gray";
  }
}

export function reportExplanation(report: VerificationReport, status: ReportStatus): string {
  const counts = countClaims(report.claims);
  const missing = missingCoreClaims(report.claims);
  const parts: string[] = [];
  parts.push(`${counts.confirmed} of ${counts.total} claims confirmed.`);
  if (counts.conflicting) parts.push(`${counts.conflicting} conflicting.`);
  if (counts.partially_confirmed) parts.push(`${counts.partially_confirmed} only partially confirmed.`);
  if (counts.unverified + counts.unavailable) parts.push(`${counts.unverified + counts.unavailable} unverified or unavailable.`);
  if (missing.length) parts.push(`Not yet checked: ${missing.join(", ").replace(/_/g, " ")}.`);
  if (status === "verified_no_conflicts") parts.push("Still confirm critical details on the official page before applying.");
  return parts.join(" ");
}
