import type { ChangeKind, ClaimChange, Snapshot, SnapshotClaim } from "@/types";
import { CLAIM_STATUS_LABEL, CLAIM_TYPE_LABEL } from "@/lib/formatters";

export type DiffSummary = "no_changes" | "confirmed_changes" | "incomplete" | "source_unavailable";

export const DIFF_SUMMARY_LABEL: Record<DiffSummary, string> = {
  no_changes: "No detected changes",
  confirmed_changes: "Confirmed changes",
  incomplete: "Incomplete comparison",
  source_unavailable: "Source unavailable",
};

export const CHANGE_LABEL: Record<ChangeKind, string> = {
  unchanged: "No detected change",
  changed: "Confirmed change",
  new_conflict: "New conflict",
  incomplete: "Incomplete comparison",
  source_unavailable: "Source unavailable",
};

function classify(before: SnapshotClaim | null, after: SnapshotClaim | null, claimLabel: string): { kind: ChangeKind; note: string } {
  if (!before && !after) return { kind: "incomplete", note: "Not present in either run." };
  if (!before) return { kind: "incomplete", note: `${claimLabel} was not checked in the earlier run, so nothing can be compared.` };
  if (!after) return { kind: "incomplete", note: `${claimLabel} is missing from the latest run.` };
  if (after.status === "unavailable") return { kind: "source_unavailable", note: "Evidence for this claim was unavailable in the latest run. This does not mean the value changed." };
  if (after.status === "conflicting" && before.status !== "conflicting") return { kind: "new_conflict", note: "Sources now disagree about this claim." };
  if (after.normalizedValue === before.normalizedValue && after.status === before.status) return { kind: "unchanged", note: "Same value and status in both runs." };
  if (before.normalizedValue !== null && after.normalizedValue !== null && before.normalizedValue !== after.normalizedValue) {
    if (after.status === "confirmed" || after.status === "partially_confirmed") {
      return { kind: "changed", note: `Value changed between runs (${before.normalizedValue} → ${after.normalizedValue}).` };
    }
    return { kind: "incomplete", note: "The value differs, but the latest evidence is not strong enough to call it a confirmed change." };
  }
  if (after.normalizedValue === before.normalizedValue) {
    return { kind: "changed", note: `Status changed from ${CLAIM_STATUS_LABEL[before.status]} to ${CLAIM_STATUS_LABEL[after.status]}.` };
  }
  return { kind: "incomplete", note: "One run has no usable value for this claim, so the comparison is incomplete." };
}

export function diffSnapshots(before: Snapshot | null, after: Snapshot): ClaimChange[] {
  const types = new Set([...(before?.claims.map((c) => c.type) ?? []), ...after.claims.map((c) => c.type)]);
  return [...types].map((type) => {
    const b = before?.claims.find((c) => c.type === type) ?? null;
    const a = after.claims.find((c) => c.type === type) ?? null;
    const { kind, note } = classify(b, a, CLAIM_TYPE_LABEL[type]);
    return { claimType: type, kind, before: b, after: a, note };
  });
}

export function summarizeDiff(changes: ClaimChange[], after: Snapshot): DiffSummary {
  if (changes.some((c) => c.kind === "changed" || c.kind === "new_conflict")) return "confirmed_changes";
  if (changes.some((c) => c.kind === "source_unavailable") || after.unavailableSources.length > 0) return "source_unavailable";
  if (changes.some((c) => c.kind === "incomplete")) return "incomplete";
  return "no_changes";
}
