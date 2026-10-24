"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SnapshotDiffView } from "@/components/history/SnapshotDiffView";
import { OpportunityPicker } from "@/components/opportunities/OpportunityPicker";
import { Card, CardHeader } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { EmptyState, ErrorState, Notice, SkeletonCards } from "@/components/ui/States";
import { ReportStatusBadge } from "@/components/verification/StatusBadges";
import { useOpportunityChoices } from "@/features/discovery/useChoices";
import { useAsync } from "@/hooks/useAsync";
import { ApiError } from "@/lib/api-errors";
import { formatDateTime } from "@/lib/date-utils";
import { RUN_STATE_LABEL } from "@/lib/formatters";
import { useDemo } from "@/providers/DemoProvider";
import { getHistory } from "./api";

export function HistoryView({ initialOpp }: { initialOpp?: string }) {
  const { demo, ready } = useDemo();
  const { choices } = useOpportunityChoices();
  const [oppId, setOppId] = useState(initialOpp ?? "");
  const [afterId, setAfterId] = useState("");
  const [beforeId, setBeforeId] = useState("");

  useEffect(() => {
    if (!oppId && choices.length) setOppId(choices[0].id);
  }, [choices, oppId]);

  const history = useAsync((s) => getHistory(demo, oppId, s), [demo, oppId], ready && !!oppId);
  const snaps = history.data ?? [];

  useEffect(() => {
    setAfterId(snaps[0]?.id ?? "");
    setBeforeId(snaps[1]?.id ?? "");
  }, [history.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const after = snaps.find((s) => s.id === afterId) ?? null;
  const before = snaps.find((s) => s.id === beforeId && s.id !== afterId) ?? null;
  const opts = snaps.map((s) => ({ value: s.id, label: `${s.runId} — ${formatDateTime(s.capturedAt)}` }));

  return (
    <div className="page">
      <PageHeader eyebrow="Snapshots over time" title="History" subtitle="Compare verification runs. VERIFAI only reports changes between runs that actually happened — it does not monitor continuously." />
      <div className="picker-row"><OpportunityPicker choices={choices} value={oppId} onChange={setOppId} /></div>

      {!oppId ? (
        <EmptyState title="Choose an opportunity">Select an opportunity to see its previous verification runs.</EmptyState>
      ) : history.loading ? <SkeletonCards count={2} /> : history.error ? (
        history.error instanceof ApiError && history.error.kind === "not_implemented" ? (
          <EmptyState title="No history available">The backend has no stored runs for this opportunity yet.</EmptyState>
        ) : <ErrorState error={history.error} onRetry={history.reload} />
      ) : snaps.length === 0 ? (
        <EmptyState title="No verification runs yet">Run a recheck to create the first snapshot. Comparisons need at least two runs.</EmptyState>
      ) : (
        <div className="grid-history">
          <Card>
            <CardHeader title={`Runs (${snaps.length})`} />
            <ol className="run-list">
              {snaps.map((s) => (
                <li key={s.id} className={s.id === afterId ? "run-latest" : s.id === beforeId ? "run-earlier" : ""}>
                  <div><strong>{s.runId}</strong><span className="small muted">{formatDateTime(s.capturedAt)}</span></div>
                  <div className="badge-row"><ReportStatusBadge status={s.reportStatus} short /><span className="small muted">{RUN_STATE_LABEL[s.runState]}</span></div>
                </li>
              ))}
            </ol>
          </Card>
          <Card>
            <CardHeader title="Compare runs" />
            {snaps.length < 2 && <Notice tone="info" title="Only one run">A second run is needed before changes can be detected.</Notice>}
            <div className="picker-row picker-row-2">
              <Select label="Earlier run" hideLabel={false} value={beforeId} onChange={setBeforeId} options={[{ value: "", label: "None" }, ...opts]} />
              <Select label="Later run" hideLabel={false} value={afterId} onChange={setAfterId} options={opts} />
            </div>
            {after && <SnapshotDiffView before={before} after={after} />}
          </Card>
        </div>
      )}
    </div>
  );
}
