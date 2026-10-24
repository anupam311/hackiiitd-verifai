"use client";

import Link from "next/link";
import { ArrowLeft, FileBadge2 } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LinkButton } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonCards } from "@/components/ui/States";
import { ReportView } from "@/components/verification/ReportView";
import { RecheckButton } from "@/components/opportunities/RecheckButton";
import { getOpportunity } from "@/features/discovery/api";
import { getReport } from "@/features/verification/api";
import { useAsync } from "@/hooks/useAsync";
import { ApiError } from "@/lib/api-errors";
import { useDemo } from "@/providers/DemoProvider";

export default function ReportPage({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id);
  const { demo, ready } = useDemo();
  const opp = useAsync((s) => getOpportunity(demo, id, s), [demo, id], ready);
  const report = useAsync((s) => getReport(demo, id, s), [demo, id], ready);
  const noReport = report.error instanceof ApiError && report.error.kind === "not_implemented";

  return (
    <div className="page">
      <Link href={`/opportunities/${encodeURIComponent(id)}?tab=report`} className="back-link">
        <ArrowLeft size={15} aria-hidden /> Back to opportunity
      </Link>
      <PageHeader
        eyebrow="Verification report"
        title={opp.data?.title ?? "Verification report"}
        subtitle={opp.data ? `${opp.data.organization ?? "Organisation unknown"} — claim-level evidence, conflicts and limitations.` : undefined}
        actions={
          <>
            <LinkButton href={`/passport/${encodeURIComponent(id)}`} icon={<FileBadge2 size={15} aria-hidden />}>Verification Passport</LinkButton>
            <RecheckButton opportunityId={id} size="md" variant="primary" label="Recheck now" />
          </>
        }
      />
      {report.loading || !ready ? <SkeletonCards count={3} label="Loading report" /> : noReport ? (
        <EmptyState title="No verification report yet" action={<RecheckButton opportunityId={id} size="md" variant="primary" label="Run a recheck" />}>Nothing has been verified for this opportunity yet.</EmptyState>
      ) : report.error ? (
        <ErrorState error={report.error} onRetry={report.reload} />
      ) : report.data ? (
        <ReportView report={report.data} />
      ) : null}
    </div>
  );
}
