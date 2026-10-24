"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useMemo } from "react";
import { ChecklistView } from "@/components/checklist/ChecklistView";
import { PageHeader } from "@/components/layout/PageHeader";
import { Notice, EmptyState, ErrorState, SkeletonCards } from "@/components/ui/States";
import { getOpportunity } from "@/features/discovery/api";
import { getReport } from "@/features/verification/api";
import { useAsync } from "@/hooks/useAsync";
import { ApiError } from "@/lib/api-errors";
import { useDemo } from "@/providers/DemoProvider";
import { buildChecklist } from "./build";
import { useChecklistProgress } from "./store";

export function ChecklistPage({ id }: { id: string }) {
  const { demo, ready } = useDemo();
  const opp = useAsync((s) => getOpportunity(demo, id, s), [demo, id], ready);
  const report = useAsync(async (s) => {
    try { return await getReport(demo, id, s); } catch (e) { if (e instanceof ApiError && e.kind === "not_implemented") return null; throw e; }
  }, [demo, id], ready);
  const progress = useChecklistProgress(id);
  const items = useMemo(() => (opp.data ? buildChecklist(opp.data, report.data) : []), [opp.data, report.data]);

  return (
    <div className="page">
      <Link href="/checklist" className="back-link"><ArrowLeft size={15} aria-hidden /> All checklists</Link>
      {opp.loading || !ready ? <SkeletonCards count={2} /> : opp.error || !opp.data ? (
        <ErrorState error={opp.error ?? new Error("Opportunity not found")} onRetry={opp.reload} />
      ) : (
        <>
          <PageHeader eyebrow="Application checklist" title={opp.data.title} subtitle={`${opp.data.organization ?? "Organisation unknown"} — built from the application instructions VERIFAI found.`} />
          <Notice tone="info" title="You submit the application yourself">VERIFAI does not submit applications for you. Ticks are stored in this browser only.</Notice>
          {items.length === 0 ? <EmptyState title="No checklist items">No application instructions were found.</EmptyState> : (
            <ChecklistView items={items} isDone={progress.isDone} onToggle={progress.toggle} onReset={progress.reset} />
          )}
        </>
      )}
    </div>
  );
}
