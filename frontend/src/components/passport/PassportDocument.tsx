import type { ApplicantProfile, EligibilityAnalysis, Opportunity, Snapshot, VerificationReport } from "@/types";
import { LogoMark } from "@/components/layout/Logo";
import { ReportStatusBadge, ClaimStatusBadge } from "@/components/verification/StatusBadges";
import { Badge } from "@/components/ui/Badge";
import { ExternalLink } from "@/components/ui/Button";
import { FIT_LABEL } from "@/features/matching/match";
import { CHANGE_LABEL, DIFF_SUMMARY_LABEL, diffSnapshots, summarizeDiff } from "@/features/history/diff";
import { formatDate, formatDateTime } from "@/lib/date-utils";
import { CATEGORY_LABEL, CLAIM_TYPE_LABEL, SOURCE_TYPE_LABEL } from "@/lib/formatters";
import { countClaims, coverageScore, deriveReportStatus, reportExplanation } from "@/lib/verification";

export interface PassportProps {
  opportunity: Opportunity;
  report: VerificationReport | null;
  history: Snapshot[];
  generatedAt: string;
  /** Only provided when the user explicitly opts in. */
  fit: { analysis: EligibilityAnalysis; profile: Pick<ApplicantProfile, "educationLevel" | "fieldOfStudy" | "graduationYear"> } | null;
}

/** Printable, shareable report. Contains no applicant profile data unless `fit` is passed. */
export function PassportDocument({ opportunity: o, report, history, generatedAt, fit }: PassportProps) {
  const status = report ? deriveReportStatus(report.claims) : null;
  const counts = report ? countClaims(report.claims) : null;
  const score = counts ? coverageScore(counts) : null;
  const diff = history.length >= 2 ? (() => { const ch = diffSnapshots(history[1], history[0]); return { ch, summary: summarizeDiff(ch, history[0]) }; })() : null;
  const sourceName = new Map((report?.sources ?? []).map((s) => [s.id, s]));
  const conflicts = report?.claims.filter((c) => c.status === "conflicting") ?? [];

  return (
    <article className="passport" aria-label="Verification Passport">
      <header className="passport-head">
        <LogoMark size={38} />
        <div>
          <p className="eyebrow">VERIFAI</p>
          <h1>Verification Passport</h1>
          <p className="muted small">Generated {formatDateTime(generatedAt)} · evidence-first report, not a guarantee of authenticity</p>
        </div>
        {status && <div className="passport-status"><ReportStatusBadge status={status} /></div>}
      </header>

      {(o.isSample || report?.isSample) && <p className="passport-sample">SAMPLE DATA — fictional organisations and invented evidence from a development fixture.</p>}

      <section>
        <h2>1. Opportunity</h2>
        <dl className="kv kv-2">
          <div><dt>Title</dt><dd>{o.title}</dd></div>
          <div><dt>Organisation</dt><dd>{o.organization ?? "Unknown"}</dd></div>
          <div><dt>Category</dt><dd>{CATEGORY_LABEL[o.category]}</dd></div>
          <div><dt>Location</dt><dd>{o.location ?? "Unknown"}</dd></div>
          <div><dt>Listed deadline</dt><dd>{o.deadline ? formatDate(o.deadline) : o.deadlineText ?? "Unknown — not stated in retrieved sources"}</dd></div>
          <div><dt>Opportunity ID</dt><dd>{o.id}</dd></div>
          <div><dt>Original source</dt><dd>{o.canonicalUrl ? <ExternalLink href={o.canonicalUrl}>{o.canonicalUrl}</ExternalLink> : "Not recorded"}</dd></div>
          <div><dt>Application URL</dt><dd>{o.applicationUrl ? <ExternalLink href={o.applicationUrl}>{o.applicationUrl}</ExternalLink> : "Not found"}</dd></div>
        </dl>
      </section>

      <section>
        <h2>2. Report status</h2>
        {report && status && counts ? (
          <>
            <p>{reportExplanation(report, status)}</p>
            <p className="small muted">Report generated {formatDateTime(report.generatedAt)} · run {report.runId ?? "n/a"}</p>
            {score && <p className="small"><b>Evidence coverage {score.percent}%</b> — {score.formula}. {score.caveat}</p>}
          </>
        ) : <p>No verification report exists. Nothing about this opportunity has been verified.</p>}
      </section>

      {report && (
        <>
          <section>
            <h2>3. Claim-level findings</h2>
            {report.claims.map((c) => (
              <div key={c.id} className="passport-claim">
                <div className="passport-claim-head"><strong>{CLAIM_TYPE_LABEL[c.type]}</strong><ClaimStatusBadge status={c.status} /></div>
                <p className="small"><b>Original wording:</b> {c.originalWording ?? "Not recorded"} · <b>Normalised:</b> {c.normalizedValue ?? "None"}</p>
                <p className="small">{c.explanation}</p>
                {c.evidence.map((e, i) => {
                  const s = sourceName.get(e.sourceId);
                  return (
                    <blockquote key={i} className="passport-evidence">
                      {e.excerpt ? <>“{e.excerpt}”</> : <em>No excerpt stored.</em>}
                      <cite>{s?.name ?? "Unknown source"} · {s?.url} · retrieved {formatDateTime(s?.retrievedAt)}{e.locator ? ` · ${e.locator}` : ""}</cite>
                    </blockquote>
                  );
                })}
              </div>
            ))}
          </section>

          <section>
            <h2>4. Sources</h2>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th scope="col">Source</th><th scope="col">Type</th><th scope="col">URL</th><th scope="col">Retrieved</th><th scope="col">Outcome</th></tr></thead>
                <tbody>
                  {report.sources.map((s) => (
                    <tr key={s.id}><td>{s.name}</td><td>{SOURCE_TYPE_LABEL[s.sourceType]}</td><td className="url-cell">{s.url}</td><td>{formatDateTime(s.retrievedAt)}</td><td>{s.outcome === "ok" ? "Retrieved" : `${s.outcome.replace("_", " ")}${s.note ? ` — ${s.note}` : ""}`}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2>5. Unresolved conflicts and questions</h2>
            {conflicts.length === 0 && report.unresolvedQuestions.length === 0 ? <p>None recorded.</p> : (
              <ul className="plain-list">
                {conflicts.map((c) => <li key={c.id}><b>Conflict — {CLAIM_TYPE_LABEL[c.type]}:</b> {c.normalizedValue}</li>)}
                {report.unresolvedQuestions.map((q) => <li key={q}>{q}</li>)}
              </ul>
            )}
          </section>
        </>
      )}

      {diff && (
        <section>
          <h2>6. Historical changes</h2>
          <p className="small"><Badge tone="gray">{DIFF_SUMMARY_LABEL[diff.summary]}</Badge> {formatDateTime(history[1].capturedAt)} → {formatDateTime(history[0].capturedAt)}</p>
          <ul className="plain-list small">
            {diff.ch.filter((c) => c.kind !== "unchanged").map((c) => <li key={c.claimType}><b>{CLAIM_TYPE_LABEL[c.claimType]}:</b> {CHANGE_LABEL[c.kind]} — {c.note}</li>)}
            {diff.ch.every((c) => c.kind === "unchanged") && <li>No detected changes between the two most recent runs.</li>}
          </ul>
        </section>
      )}

      {fit && (
        <section>
          <h2>7. Eligibility fit (included by the applicant)</h2>
          <p className="small"><b>{FIT_LABEL[fit.analysis.fit]}</b> — {fit.analysis.counts.match} match, {fit.analysis.counts.mismatch} no match, {fit.analysis.counts.unknown} unknown.</p>
          <ul className="plain-list small">{fit.analysis.reasons.map((r) => <li key={r.requirementId}><b>{r.requirement}:</b> {r.outcome} — {r.reasoning}</li>)}</ul>
        </section>
      )}

      <section>
        <h2>Verification limitations</h2>
        <ul className="plain-list small">
          {(report?.limitations ?? []).map((l) => <li key={l}>{l}</li>)}
          <li>This passport reflects source pages as retrieved at the times shown. Pages can change, and a missing or unreachable page is not evidence that an opportunity is closed.</li>
          <li>Official-source identification is evidence about authority, not proof that every claim is true. Confirm critical details on the official page before applying.</li>
          <li>The coverage score measures how many claims have supporting evidence; it is not a probability of authenticity.</li>
        </ul>
      </section>
    </article>
  );
}
