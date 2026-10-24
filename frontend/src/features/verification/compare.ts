import type { ClaimType, SourceComparison, SourceComparisonRow, VerificationReport } from "@/types";
import { CLAIM_TYPE_LABEL } from "@/lib/formatters";

/**
 * Derive a claim-by-source comparison from the evidence already attached to a
 * report. Used when the backend `/sources` endpoint is unavailable and for
 * fixtures. Never invents values: a source that did not state a claim is null.
 */
export function buildComparison(report: VerificationReport): SourceComparison {
  const rows: SourceComparisonRow[] = report.claims
    .filter((c) => c.evidence.length > 0 || c.status === "conflicting")
    .map((claim) => {
      const values: Record<string, string | null> = {};
      for (const s of report.sources) values[s.id] = null;
      for (const e of claim.evidence) values[e.sourceId] = e.extractedValue ?? null;
      const stated = Object.values(values).filter((v): v is string => v !== null);
      const distinct = new Set(stated.map((v) => v.trim().toLowerCase()));
      let agreement: SourceComparisonRow["agreement"];
      // The claim's own status (assigned by the verification policy engine) is authoritative:
      // differently formatted text between sources is not, by itself, a conflict.
      if (stated.length === 0) agreement = "missing";
      else if (claim.status === "conflicting") agreement = "conflict";
      else if (stated.length === 1) agreement = "single_source";
      else if (distinct.size === 1 || claim.status === "confirmed") agreement = "agree";
      else agreement = "partial";
      return { claimType: claim.type as ClaimType, values, agreement, summary: summarize(claim.type, agreement, stated.length, claim.explanation) };
    });
  return { opportunityId: report.opportunityId, sources: report.sources, rows, isSample: report.isSample };
}

function summarize(type: ClaimType, agreement: SourceComparisonRow["agreement"], statedCount: number, explanation: string): string {
  const label = CLAIM_TYPE_LABEL[type];
  switch (agreement) {
    case "agree":
      return `${label}: ${statedCount} sources state the same value.`;
    case "conflict":
      return `${label}: sources state different values. ${explanation}`;
    case "partial":
      return `${label}: sources are consistent but differ in detail. ${explanation}`;
    case "single_source":
      return `${label}: only one source states this, so independent corroboration is limited.`;
    default:
      return `${label}: no retrieved source states a value.`;
  }
}
