import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { Run, RunStepId } from "@/types";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Notice } from "@/components/ui/States";
import { formatDateTime } from "@/lib/date-utils";
import { describeError } from "@/lib/api-errors";
import { RUN_STATE_LABEL } from "@/lib/formatters";

const STEPS: { id: RunStepId; label: string }[] = [
  { id: "request_received", label: "Search request received" },
  { id: "discovering", label: "Discovering candidate opportunities" },
  { id: "retrieving_sources", label: "Retrieving source pages" },
  { id: "extracting_claims", label: "Extracting candidate claims" },
  { id: "comparing_claims", label: "Comparing claims against evidence" },
  { id: "detecting_conflicts", label: "Detecting conflicts and missing evidence" },
  { id: "building_report", label: "Building the report" },
  { id: "finished", label: "Finished" },
];

const STATE_TONE: Record<Run["state"], Tone> = { queued: "gray", running: "blue", completed: "green", partial: "amber", failed: "red", cancelled: "gray" };

/**
 * Renders the steps of a backend run. Each row is driven by an event the backend
 * returned; steps with no event say so. There are no timers or invented percentages.
 */
export function RunTimeline({ run, error, emptyMessage }: { run: Run | null; error?: unknown; emptyMessage?: string }) {
  if (error) {
    const d = describeError(error);
    return (
      <Notice tone="danger" title={`Could not read run progress — ${d.title}`}>
        {d.message}
      </Notice>
    );
  }
  if (!run) {
    return <p className="muted small">{emptyMessage ?? "No run is in progress."}</p>;
  }
  const latest = new Map(run.events.map((e) => [e.step, e]));
  const finishedLabel = run.state === "completed" ? "Completed" : run.state === "partial" ? "Partially completed" : run.state === "failed" ? "Failed" : "Finished";

  return (
    <div className="timeline-wrap">
      <div className="timeline-head">
        <Badge tone={STATE_TONE[run.state]}>{RUN_STATE_LABEL[run.state]}</Badge>
        {run.isSample && <Badge tone="purple">Sample run log</Badge>}
        <span className="muted small">Run {run.id}</span>
      </div>
      <ol className="timeline" aria-label="Run progress">
        {STEPS.map((s) => {
          const ev = latest.get(s.id);
          const label = s.id === "finished" ? (ev ? finishedLabel : "Completed, partially completed or failed") : s.label;
          const state = ev?.state ?? "none";
          return (
            <li key={s.id} className={`tl-step tl-${state}`}>
              <span className="tl-icon" aria-hidden>
                {state === "completed" ? <CheckCircle2 size={18} /> : state === "failed" ? <XCircle size={18} /> : state === "started" ? <Loader2 size={18} className="spin" /> : <Circle size={18} />}
              </span>
              <div>
                <strong>{label}</strong>
                <p className="small muted">
                  {ev ? (
                    <>
                      {ev.message ? `${ev.message} · ` : ""}
                      {formatDateTime(ev.at)}
                    </>
                  ) : (
                    "No event reported for this step"
                  )}
                </p>
              </div>
              <span className="sr-only">{state === "none" ? "No event" : state}</span>
            </li>
          );
        })}
      </ol>
      {run.warnings.length > 0 && (
        <ul className="warnings">
          {run.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
