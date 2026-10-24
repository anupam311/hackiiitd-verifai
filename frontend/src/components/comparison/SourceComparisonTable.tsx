import type { SourceComparison, SourceComparisonRow } from "@/types";
import { Badge, type Tone } from "@/components/ui/Badge";
import { ExternalLink } from "@/components/ui/Button";
import { Notice } from "@/components/ui/States";
import { formatDateTime } from "@/lib/date-utils";
import { CLAIM_TYPE_LABEL, SOURCE_TYPE_LABEL } from "@/lib/formatters";

const AGREE: Record<SourceComparisonRow["agreement"], { label: string; tone: Tone }> = {
  agree: { label: "Agree", tone: "green" },
  partial: { label: "Partly agree", tone: "amber" },
  conflict: { label: "Conflict", tone: "red" },
  single_source: { label: "Single source", tone: "gray" },
  missing: { label: "Not stated", tone: "gray" },
};

/** Claim × source matrix. Conflicts are highlighted; a missing value is shown as such, never filled in. */
export function SourceComparisonTable({ comparison }: { comparison: SourceComparison }) {
  const { sources, rows } = comparison;
  if (sources.length === 0) return <p className="muted">No sources were retrieved, so there is nothing to compare.</p>;

  return (
    <div className="stack">
      {sources.length === 1 && (
        <Notice tone="info" title="One source only">
          Independent corroboration is limited: every value below comes from {sources[0].name}.
        </Notice>
      )}
      <div className="table-wrap" role="region" aria-label="Source comparison table, scrollable" tabIndex={0}>
        <table className="table compare-table">
          <caption className="sr-only">Claims compared across sources</caption>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              {sources.map((s) => (
                <th scope="col" key={s.id}>
                  <span className="src-head">
                    <strong>{s.name}</strong>
                    <Badge tone={s.sourceType === "official" || s.sourceType === "institution" || s.sourceType === "employer" ? "green" : "gray"}>{SOURCE_TYPE_LABEL[s.sourceType]}</Badge>
                    {s.outcome !== "ok" && <Badge tone="gray">Unavailable</Badge>}
                    <small>{formatDateTime(s.retrievedAt)}</small>
                    <ExternalLink href={s.url}>Inspect ↗</ExternalLink>
                  </span>
                </th>
              ))}
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.claimType} className={r.agreement === "conflict" ? "row-conflict" : undefined}>
                <th scope="row">{CLAIM_TYPE_LABEL[r.claimType]}</th>
                {sources.map((s) => {
                  const v = r.values[s.id];
                  return (
                    <td key={s.id} data-label={s.name}>
                      {v ?? <span className="muted">{s.outcome !== "ok" ? "Source unavailable" : "Not stated"}</span>}
                    </td>
                  );
                })}
                <td data-label="Result">
                  <Badge tone={AGREE[r.agreement].tone}>{AGREE[r.agreement].label}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="disclosure" open={rows.some((r) => r.agreement === "conflict")}>
        <summary>What differs and what remains unresolved</summary>
        <ul className="plain-list small disclosure-body">
          {rows.filter((r) => r.agreement !== "agree").map((r) => (
            <li key={r.claimType}>{r.summary}</li>
          ))}
          {rows.every((r) => r.agreement === "agree") && <li>All compared claims match across the retrieved sources. Matching sources are still not proof that a value is correct.</li>}
        </ul>
      </details>
      <p className="muted small">Official-source identification is evidence about source authority; it is not automatic proof that every claim on that page is true or current.</p>
    </div>
  );
}
