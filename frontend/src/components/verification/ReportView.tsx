import type { ReactNode } from "react";
import type { VerificationReport } from "@/types";
import { Card, CardHeader } from "@/components/ui/Card";
import { SourceCard } from "@/components/evidence/SourceCard";
import { Notice } from "@/components/ui/States";
import { formatDateTime } from "@/lib/date-utils";
import { countClaims, deriveReportStatus, missingCoreClaims, reportExplanation } from "@/lib/verification";
import { CLAIM_TYPE_LABEL } from "@/lib/formatters";
import { ClaimTable } from "./ClaimTable";
import { CoverageSummary } from "./CoverageSummary";
import { ReportStatusBanner } from "./ReportStatusBanner";
import { UnresolvedList } from "./UnresolvedList";

/** Full verification report: status, coverage, claim table with evidence, unresolved questions, sources, limitations. */
export function ReportView({ report, actions }: { report: VerificationReport; actions?: ReactNode }) {
  const status = deriveReportStatus(report.claims);
  const counts = countClaims(report.claims);
  const missing = missingCoreClaims(report.claims);

  return (
    <div className="stack">
      <ReportStatusBanner status={status} actions={actions}>
        {report.claims.length === 0 ? "No claims have been checked yet." : reportExplanation(report, status)}{" "}
        <span className="muted">Generated {formatDateTime(report.generatedAt, "at an unknown time")}.</span>
      </ReportStatusBanner>

      {report.isSample && (
        <Notice tone="info" title="Sample report">
          This report is a development fixture with invented organisations and evidence.
        </Notice>
      )}
      {missing.length > 0 && (
        <Notice tone="warn" title="Important claims were not checked">
          No result exists for: {missing.map((m) => CLAIM_TYPE_LABEL[m].toLowerCase()).join(", ")}. This opportunity is not treated as verified.
        </Notice>
      )}
      {report.sources.length === 1 && report.claims.length > 0 && (
        <Notice tone="info" title="Limited corroboration">
          Only one source was retrieved, so independent corroboration is limited. A single source can be wrong or out of date.
        </Notice>
      )}

      <div className="grid-report">
        <Card>
          <CardHeader title="Coverage" />
          <CoverageSummary counts={counts} />
        </Card>
        <Card>
          <CardHeader title="Claim verification" />
          <ClaimTable claims={report.claims} sources={report.sources} />
        </Card>
      </div>

      <div className="grid-2">
        <Card>
          <CardHeader title="Unresolved questions" />
          <UnresolvedList questions={report.unresolvedQuestions} />
        </Card>
        <Card>
          <CardHeader title="Verification limitations" />
          {report.limitations.length ? (
            <ul className="plain-list small">
              {report.limitations.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          ) : (
            <p className="muted small">No limitations were recorded. Source pages can change after retrieval; confirm critical details on the official page.</p>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title={`Sources (${report.sources.length})`} />
        {report.sources.length === 0 ? <p className="muted">No sources were retrieved for this report.</p> : (
          <div className="source-grid">
            {report.sources.map((s) => (
              <SourceCard key={s.id} source={s} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
