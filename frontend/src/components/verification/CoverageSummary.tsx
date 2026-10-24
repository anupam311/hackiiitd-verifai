import type { ClaimCounts } from "@/types";
import { Disclosure } from "@/components/ui/Disclosure";
import { Dot } from "@/components/ui/Badge";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { coverageScore } from "@/lib/verification";

/** Counts per status plus a transparent coverage score. The score is explicitly not a probability. */
export function CoverageSummary({ counts }: { counts: ClaimCounts }) {
  const score = coverageScore(counts);
  const tone = !score ? "gray" : score.percent >= 80 ? "green" : score.percent >= 40 ? "amber" : "gray";
  return (
    <div className="coverage">
      <div className="coverage-top">
        <ProgressRing percent={score?.percent ?? null} tone={tone} label="coverage" />
        <div>
          <strong>Evidence coverage</strong>
          <p className="muted small">
            {score ? `${score.points} of ${score.total} claim points supported by evidence.` : "No claims have been checked yet."}
          </p>
        </div>
      </div>
      <ul className="status-list" aria-label="Claims by status">
        <li>
          <Dot tone="green" /> Confirmed <b>{counts.confirmed}</b>
        </li>
        <li>
          <Dot tone="amber" /> Partially confirmed <b>{counts.partially_confirmed}</b>
        </li>
        <li>
          <Dot tone="red" /> Conflicting <b>{counts.conflicting}</b>
        </li>
        <li>
          <Dot tone="gray" /> Unverified <b>{counts.unverified}</b>
        </li>
        <li>
          <Dot tone="gray" /> Unavailable <b>{counts.unavailable}</b>
        </li>
      </ul>
      {score && (
        <Disclosure summary="How is this calculated?">
          <p className="small">{score.formula}</p>
          <p className="small muted">{score.caveat}</p>
        </Disclosure>
      )}
    </div>
  );
}
