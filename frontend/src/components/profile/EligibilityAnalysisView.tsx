import Link from "next/link";
import { CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import type { EligibilityAnalysis, MatchOutcome, MatchReason } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { FIT_LABEL } from "@/features/matching/match";

const GROUPS: { outcome: MatchOutcome; title: string; icon: typeof CheckCircle2; cls: string }[] = [
  { outcome: "match", title: "Appears to match your profile", icon: CheckCircle2, cls: "fit-yes" },
  { outcome: "mismatch", title: "Does not appear to match", icon: XCircle, cls: "fit-no" },
  { outcome: "unknown", title: "Cannot be determined", icon: HelpCircle, cls: "fit-unknown" },
];

function Group({ title, items, icon: Icon, cls }: { title: string; items: MatchReason[]; icon: typeof CheckCircle2; cls: string }) {
  if (items.length === 0) return null;
  return (
    <div className="elig-group">
      <h4>
        {title} <span className="muted">({items.length})</span>
      </h4>
      <ul>
        {items.map((r) => (
          <li key={r.requirementId} className={cls}>
            <Icon size={16} aria-hidden />
            <div>
              <strong>{r.requirement}</strong>
              <p className="small muted">{r.reasoning}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Eligibility analysis: separate from verification status and evidence quality. */
export function EligibilityAnalysisView({ analysis }: { analysis: EligibilityAnalysis }) {
  return (
    <div className="elig">
      <div className="elig-head">
        <Badge tone={analysis.fit === "strong" ? "purple" : analysis.fit === "partial" ? "blue" : "gray"}>{FIT_LABEL[analysis.fit]}</Badge>
        <span className="small muted">
          {analysis.counts.match} match · {analysis.counts.mismatch} no match · {analysis.counts.unknown} unknown
        </span>
      </div>
      {analysis.profileIncomplete && (
        <p className="small">
          Your applicant profile is empty, so nothing can be evaluated. <Link href="/profile" className="link">Complete your profile →</Link>
        </p>
      )}
      {analysis.reasons.length === 0 && <p className="muted small">No structured eligibility requirements were extracted for this opportunity, so no analysis is possible. Read the official page.</p>}
      {GROUPS.map((g) => (
        <Group key={g.outcome} title={g.title} items={analysis.reasons.filter((r) => r.outcome === g.outcome)} icon={g.icon} cls={g.cls} />
      ))}
      <p className="small muted">Unknown requirements are never treated as satisfied. This analysis compares your profile with listed requirements; it says nothing about whether the opportunity is authentic or well evidenced.</p>
    </div>
  );
}
