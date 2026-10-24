"use client";

import Link from "next/link";
import { X } from "lucide-react";
import type { Opportunity, VerificationReport } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { ReportStatusBadge, NoReportBadge } from "@/components/verification/StatusBadges";
import { useCompare } from "@/features/comparison/CompareProvider";
import { getReport } from "@/features/verification/api";
import { useAsync } from "@/hooks/useAsync";
import { ApiError } from "@/lib/api-errors";
import { formatDate } from "@/lib/date-utils";
import { CATEGORY_LABEL, WORK_MODE_LABEL } from "@/lib/formatters";
import { countClaims, coverageScore, deriveReportStatus } from "@/lib/verification";
import { useDemo } from "@/providers/DemoProvider";

const STATE = { open: "Listed as open", closed: "Listed as closed", rolling: "Rolling", unknown: "Unknown" } as const;

function Unknown({ children = "Unknown" }: { children?: string }) {
  return <span className="unknown-cell">{children}</span>;
}

function evidenceQuality(r: VerificationReport | null) {
  if (!r) return <Unknown>No report</Unknown>;
  const official = r.sources.filter((s) => ["official", "institution", "employer"].includes(s.sourceType)).length;
  const failed = r.sources.filter((s) => s.outcome !== "ok").length;
  const stale = r.sources.filter((s) => s.freshness === "stale").length;
  return (
    <span>
      {r.sources.length} source{r.sources.length === 1 ? "" : "s"}, {official} official/authoritative
      {failed > 0 && <>, <b>{failed} unavailable</b></>}
      {stale > 0 && <>, {stale} possibly stale</>}
      {r.sources.length === 1 && <><br /><span className="muted small">Single source: limited corroboration</span></>}
    </span>
  );
}

/** Side-by-side comparison. Unknown values are shown as unknown, never silently replaced. */
export function OpportunityCompareTable({ opportunities }: { opportunities: Opportunity[] }) {
  const { demo, ready } = useDemo();
  const { toggle, clear } = useCompare();
  const ids = opportunities.map((o) => o.id).join("|");
  const reports = useAsync(
    async (signal) => {
      const entries = await Promise.all(
        opportunities.map(async (o) => {
          try {
            return [o.id, await getReport(demo, o.id, signal)] as const;
          } catch (e) {
            if (e instanceof ApiError && e.kind === "not_implemented") return [o.id, null] as const;
            throw e;
          }
        }),
      );
      return Object.fromEntries(entries) as Record<string, VerificationReport | null>;
    },
    [demo, ids],
    ready && opportunities.length > 0,
  );

  if (reports.error) return <ErrorState error={reports.error} onRetry={reports.reload} />;
  const R = reports.data ?? {};

  const rows: { label: string; cell: (o: Opportunity) => React.ReactNode }[] = [
    { label: "Category", cell: (o) => CATEGORY_LABEL[o.category] },
    { label: "Eligibility (as listed)", cell: (o) => o.eligibilitySummary ?? <Unknown>Not stated</Unknown> },
    { label: "Deadline (as listed)", cell: (o) => (o.deadline ? formatDate(o.deadline) : o.deadlineText ?? <Unknown>Unknown</Unknown>) },
    { label: "Application status (as listed)", cell: (o) => (o.applicationState === "unknown" ? <Unknown /> : STATE[o.applicationState]) },
    { label: "Location", cell: (o) => (o.location ? `${o.location}${o.workMode !== "unknown" ? ` · ${WORK_MODE_LABEL[o.workMode]}` : ""}` : <Unknown />) },
    { label: "Duration", cell: (o) => o.durationText ?? <Unknown>Not stated</Unknown> },
    {
      label: "Stipend / funding",
      cell: (o) => {
        const c = R[o.id]?.claims.find((x) => x.type === "stipend");
        if (c?.status === "conflicting") return <><span>{c.normalizedValue}</span> <Badge tone="red">Conflicting</Badge></>;
        return o.stipendText ?? <Unknown>Not stated</Unknown>;
      },
    },
    {
      label: "Verification status",
      cell: (o) => (R[o.id] ? <ReportStatusBadge status={deriveReportStatus(R[o.id]!.claims)} short /> : reports.loading ? "Loading…" : <NoReportBadge />),
    },
    {
      label: "Verification completeness",
      cell: (o) => {
        const r = R[o.id];
        if (!r) return <Unknown>No report</Unknown>;
        const c = countClaims(r.claims);
        const s = coverageScore(c);
        return <span>{c.confirmed} of {c.total} confirmed{s ? ` · coverage ${s.percent}%` : ""}{c.conflicting > 0 && <> · <b>{c.conflicting} conflicting</b></>}</span>;
      },
    },
    { label: "Source evidence quality", cell: (o) => (reports.loading ? "Loading…" : evidenceQuality(R[o.id] ?? null)) },
  ];

  return (
    <div className="stack">
      <div className="table-wrap" role="region" aria-label="Opportunity comparison, scrollable" tabIndex={0}>
        <table className="table compare-table opp-compare">
          <caption className="sr-only">Selected opportunities compared side by side</caption>
          <thead>
            <tr>
              <th scope="col">Compare</th>
              {opportunities.map((o) => (
                <th scope="col" key={o.id}>
                  <span className="src-head">
                    <Link href={`/opportunities/${encodeURIComponent(o.id)}`}><strong>{o.title}</strong></Link>
                    <small>{o.organization}</small>
                    <Button size="sm" variant="ghost" icon={<X size={13} aria-hidden />} onClick={() => toggle(o)} aria-label={`Remove ${o.title} from comparison`}>Remove</Button>
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row">{row.label}</th>
                {opportunities.map((o) => (
                  <td key={o.id} data-label={o.title}>{row.cell(o)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div><Button variant="ghost" onClick={clear}>Clear selection</Button></div>
    </div>
  );
}
