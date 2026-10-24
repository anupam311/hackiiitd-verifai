import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import type { SourceComparison } from "@/types";
import { CLAIM_TYPE_LABEL } from "@/lib/formatters";

/** Prominent callout for rows where sources disagree. Renders nothing without conflicts. */
export function ConflictBanner({ comparison, action }: { comparison: SourceComparison; action?: ReactNode }) {
  const conflicts = comparison.rows.filter((r) => r.agreement === "conflict");
  if (conflicts.length === 0) return null;
  const nameOf = new Map(comparison.sources.map((s) => [s.id, s.name]));
  return (
    <div className="conflict-banner" role="alert">
      <AlertTriangle size={22} aria-hidden />
      <div>
        <strong>Conflicting information found</strong>
        <ul>
          {conflicts.map((r) => (
            <li key={r.claimType}>
              <b>{CLAIM_TYPE_LABEL[r.claimType]}:</b>{" "}
              {Object.entries(r.values)
                .filter(([, v]) => v !== null)
                .map(([sid, v]) => `${nameOf.get(sid) ?? sid}: ${v}`)
                .join(" · ")}
            </li>
          ))}
        </ul>
        <p>Both values stay visible. Review the sources and use the official page for the most accurate information.</p>
      </div>
      {action}
    </div>
  );
}
