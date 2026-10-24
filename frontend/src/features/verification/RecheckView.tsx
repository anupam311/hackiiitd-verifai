"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SnapshotDiffView } from "@/components/history/SnapshotDiffView";
import { OpportunityPicker } from "@/components/opportunities/OpportunityPicker";
import { RecheckButton } from "@/components/opportunities/RecheckButton";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, Notice, SkeletonCards } from "@/components/ui/States";
import { RunTimeline } from "@/components/verification/RunTimeline";
import { useOpportunityChoices } from "@/features/discovery/useChoices";
import { getHistory } from "@/features/history/api";
import { useRun } from "@/features/verification/useRun";
import { useAsync } from "@/hooks/useAsync";
import { useDemo } from "@/providers/DemoProvider";

export function RecheckView({ initialOpp, initialRun }: { initialOpp?: string; initialRun?: string }) {
  const { demo, ready } = useDemo();
  const { choices, loading } = useOpportunityChoices();
  const [oppId, setOppId] = useState(initialOpp ?? "");

  useEffect(() => {
    if (!oppId && choices.length) setOppId(choices[0].id);
  }, [choices, oppId]);

  // Live: follow the run id returned by POST /recheck. Sample: show the stored sample run log.
  const runId = demo ? (oppId ? "sample-run" : null) : initialRun ?? null;
  const { run, error: runError } = useRun(runId, demo);
  const history = useAsync((s) => getHistory(demo, oppId, s), [demo, oppId], ready && !!oppId);
  const snaps = history.data ?? [];

  return (
    <div className="page">
      <PageHeader eyebrow="Run a fresh check" title="Recheck" subtitle="Retrieve sources again and compare against the previous snapshot. A recheck is a one-off run, not continuous monitoring." />
      <div className="picker-row">
        <OpportunityPicker choices={choices} value={oppId} onChange={setOppId} />
        {oppId && <RecheckButton opportunityId={oppId} size="md" variant="primary" label="Recheck now" />}
      </div>

      {loading && !choices.length ? <SkeletonCards count={1} /> : !oppId ? (
        <EmptyState title="Choose an opportunity to recheck">Save or discover opportunities first, then pick one here.</EmptyState>
      ) : (
        <div className="grid-2">
          <Card>
            <CardHeader title="Run progress" />
            {demo && <Notice tone="info" title="Sample run log">No run was started. This is a stored sample showing what the real event timeline looks like.</Notice>}
            <RunTimeline run={run} error={runError} emptyMessage={demo ? "Pick an opportunity." : "No run is being followed. Press “Recheck now” to start one; the steps below will come from the backend run."} />
            <p className="muted small">Cancelling is not offered because the backend does not support cancelling a run.</p>
          </Card>
          <Card>
            <CardHeader title="Latest result vs previous snapshot" />
            {history.loading ? <SkeletonCards count={1} /> : snaps.length === 0 ? (
              <p className="muted">No previous snapshots exist for this opportunity, so there is nothing to compare.</p>
            ) : (
              <>
                <SnapshotDiffView before={snaps[1] ?? null} after={snaps[0]} />
                <p className="small"><Link className="link" href={`/history?opp=${encodeURIComponent(oppId)}`}>Open full history →</Link></p>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
