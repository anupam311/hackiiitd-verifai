import type { ChangeKind, Snapshot } from "@/types";
import { Badge, type Tone } from "@/components/ui/Badge";
import { ExternalLink } from "@/components/ui/Button";
import { formatDateTime } from "@/lib/date-utils";
import { CLAIM_STATUS_LABEL, CLAIM_TYPE_LABEL, RUN_STATE_LABEL } from "@/lib/formatters";
import { CHANGE_LABEL, DIFF_SUMMARY_LABEL, diffSnapshots, summarizeDiff, type DiffSummary } from "@/features/history/diff";
import { ReportStatusBadge } from "@/components/verification/StatusBadges";

const SUMMARY_TONE: Record<DiffSummary, Tone> = { no_changes: "green", confirmed_changes: "blue", incomplete: "amber", source_unavailable: "gray" };
const CHANGE_TONE: Record<ChangeKind, Tone> = { unchanged: "gray", changed: "blue", new_conflict: "red", incomplete: "amber", source_unavailable: "gray" };

function val(c: { normalizedValue: string | null; status: keyof typeof CLAIM_STATUS_LABEL } | null) {
  if (!c) return <span className="muted">Not checked</span>;
  return (
    <span>
      {c.normalizedValue ?? <span className="muted">No value</span>}
      <small className="muted"> · {CLAIM_STATUS_LABEL[c.status]}</small>
    </span>
  );
}

/** Latest-vs-previous comparison. "No detected changes" is not claimed unless every claim matched and no source failed. */
export function SnapshotDiffView({ before, after }: { before: Snapshot | null; after: Snapshot }) {
  const changes = diffSnapshots(before, after);
  const summary = before ? summarizeDiff(changes, after) : "incomplete";

  return (
    <div className="stack">
      <div className="diff-head">
        <Badge tone={SUMMARY_TONE[summary]}>{before ? DIFF_SUMMARY_LABEL[summary] : "Incomplete comparison"}</Badge>
        <p className="small muted">
          {before ? (
            <>Comparing run <b>{before.runId}</b> ({formatDateTime(before.capturedAt)}) → <b>{after.runId}</b> ({formatDateTime(after.capturedAt)})</>
          ) : (
            <>Only one run exists (<b>{after.runId}</b>, {formatDateTime(after.capturedAt)}), so there is nothing to compare against yet.</>
          )}
        </p>
      </div>
      <div className="diff-runs">
        {[before, after].map((s, i) =>
          s ? (
            <div key={s.id} className="diff-run">
              <strong>{i === 0 ? "Earlier run" : "Latest run"}</strong>
              <ReportStatusBadge status={s.reportStatus} short />
              <span className="small muted">{RUN_STATE_LABEL[s.runState]} · {formatDateTime(s.capturedAt)}</span>
            </div>
          ) : null,
        )}
      </div>

      {before && (
        <div className="table-wrap">
          <table className="table diff-table">
            <caption className="sr-only">Claim changes between runs</caption>
            <thead><tr><th scope="col">Claim</th><th scope="col">Earlier</th><th scope="col">Latest</th><th scope="col">Result</th></tr></thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.claimType} className={c.kind === "new_conflict" ? "row-conflict" : undefined}>
                  <th scope="row" data-label="Claim">{CLAIM_TYPE_LABEL[c.claimType]}</th>
                  <td data-label="Earlier">{val(c.before)}</td>
                  <td data-label="Latest">{val(c.after)}</td>
                  <td data-label="Result">
                    <Badge tone={CHANGE_TONE[c.kind]}>{CHANGE_LABEL[c.kind]}</Badge>
                    <p className="small muted">{c.note}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {after.unavailableSources.length > 0 && (
        <div className="notice notice-warn">
          <div>
            <strong>Sources unavailable in the latest run</strong>
            <ul className="plain-list small">
              {after.unavailableSources.map((u) => (
                <li key={u.url}><ExternalLink href={u.url}>{u.url}</ExternalLink> — {u.reason}. Unavailability is not evidence that anything changed or closed.</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {after.runState === "failed" && <p className="small muted">The latest run failed, so no changes can be confirmed.</p>}
    </div>
  );
}
