import type { ChecklistItem, Opportunity, VerificationReport } from "@/types";
import { formatDate } from "@/lib/date-utils";

export const GROUP_LABEL: Record<ChecklistItem["group"], string> = {
  eligibility: "Eligibility review",
  documents: "Required documents",
  links: "Portfolio & project links",
  form: "Application form",
  deadline: "Deadline confirmation",
  submission: "Submission requirements",
};

export const GROUP_ORDER: ChecklistItem["group"][] = ["eligibility", "documents", "links", "form", "deadline", "submission"];

/**
 * Build a checklist from application instructions that were actually extracted.
 * Nothing is added speculatively; when instructions are missing a single
 * "read the official page" item is shown instead. VERIFAI never submits applications.
 */
export function buildChecklist(opp: Opportunity, report: VerificationReport | null): ChecklistItem[] {
  const items: ChecklistItem[] = [];
  const src = opp.canonicalUrl;
  for (const r of opp.eligibility) {
    items.push({ id: `eligibility:${r.id}`, group: "eligibility", label: `Check: ${r.text}`, sourceUrl: r.sourceUrl ?? src, sourceLabel: "Programme page", done: false });
  }
  if (opp.eligibility.length === 0) {
    items.push({ id: "eligibility:read", group: "eligibility", label: "Read the eligibility criteria on the official page", detail: "No structured eligibility requirements were extracted.", sourceUrl: src, sourceLabel: "Programme page", done: false });
  }
  for (const s of opp.applicationSteps ?? []) {
    items.push({ id: `${s.group}:${s.id}`, group: s.group, label: s.label, detail: s.detail, sourceUrl: s.sourceUrl ?? src, sourceLabel: s.sourceLabel ?? null, done: false });
  }
  const deadlineClaim = report?.claims.find((c) => c.type === "deadline");
  items.push({
    id: "deadline:confirm",
    group: "deadline",
    label: opp.deadline ? `Confirm the deadline on the official page (listed: ${formatDate(opp.deadline)})` : "Find and note the deadline — none is known yet",
    detail: deadlineClaim ? `Verification status: ${deadlineClaim.status.replace(/_/g, " ")}.` : undefined,
    sourceUrl: src,
    sourceLabel: "Programme page",
    done: false,
  });
  if (!opp.applicationSteps?.length) {
    items.push({ id: "submission:read", group: "submission", label: "Read the application instructions on the official page", detail: "No step-by-step instructions were extracted.", sourceUrl: opp.applicationUrl ?? src, sourceLabel: "Application page", done: false });
  }
  return items;
}
