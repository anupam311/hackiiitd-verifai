"use client";

import Link from "next/link";
import { ArrowLeft, Download, Printer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PassportDocument } from "@/components/passport/PassportDocument";
import { Button } from "@/components/ui/Button";
import { ErrorState, Notice, SkeletonCards } from "@/components/ui/States";
import { getOpportunity } from "@/features/discovery/api";
import { getHistory } from "@/features/history/api";
import { analyzeEligibility } from "@/features/matching/match";
import { useProfile } from "@/features/profile/ProfileProvider";
import { getReport } from "@/features/verification/api";
import { useAsync } from "@/hooks/useAsync";
import { ApiError } from "@/lib/api-errors";
import { useDemo } from "@/providers/DemoProvider";

export function PassportView({ id }: { id: string }) {
  const { demo, ready } = useDemo();
  const { profile, hasProfile } = useProfile();
  const [includeFit, setIncludeFit] = useState(false);
  const [generatedAt, setGeneratedAt] = useState("");
  useEffect(() => setGeneratedAt(new Date().toISOString()), []);

  const opp = useAsync((s) => getOpportunity(demo, id, s), [demo, id], ready);
  const report = useAsync(async (s) => {
    try { return await getReport(demo, id, s); } catch (e) { if (e instanceof ApiError && e.kind === "not_implemented") return null; throw e; }
  }, [demo, id], ready);
  const history = useAsync(async (s) => {
    try { return await getHistory(demo, id, s); } catch (e) { if (e instanceof ApiError && e.kind === "not_implemented") return []; throw e; }
  }, [demo, id], ready);

  const fit = useMemo(
    () => (includeFit && opp.data ? { analysis: analyzeEligibility(opp.data, hasProfile ? profile : null), profile: { educationLevel: profile.educationLevel, fieldOfStudy: profile.fieldOfStudy, graduationYear: profile.graduationYear } } : null),
    [includeFit, opp.data, profile, hasProfile],
  );

  const download = () => {
    if (!opp.data) return;
    const payload = {
      schema: "verifai.passport.v1",
      generatedAt,
      sample: Boolean(opp.data.isSample || report.data?.isSample),
      opportunity: { id: opp.data.id, title: opp.data.title, organization: opp.data.organization, category: opp.data.category, location: opp.data.location, deadline: opp.data.deadline, deadlineText: opp.data.deadlineText ?? null, canonicalUrl: opp.data.canonicalUrl, applicationUrl: opp.data.applicationUrl },
      report: report.data,
      history: history.data ?? [],
      eligibilityFit: fit ? fit.analysis : undefined,
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `verifai-passport-${opp.data.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const loading = opp.loading || report.loading || history.loading || !ready || !generatedAt;
  const error = opp.error ?? report.error ?? history.error;

  return (
    <div className="page passport-page">
      <div className="no-print">
        <Link href={`/opportunities/${encodeURIComponent(id)}`} className="back-link"><ArrowLeft size={15} aria-hidden /> Back to opportunity</Link>
        <div className="passport-toolbar">
          <label className="check-inline">
            <input type="checkbox" checked={includeFit} onChange={(e) => setIncludeFit(e.target.checked)} />
            <span>Include my eligibility match <small className="muted">(adds profile-based reasoning; off by default)</small></span>
          </label>
          <div className="toolbar-actions">
            <Button icon={<Download size={15} aria-hidden />} onClick={download} disabled={loading || !!error}>Download JSON</Button>
            <Button variant="primary" icon={<Printer size={15} aria-hidden />} onClick={() => window.print()} disabled={loading || !!error}>Print / Save as PDF</Button>
          </div>
        </div>
        <Notice tone="info" title="Sharing">Share by saving as PDF or sending the JSON file. Public share links need a backend feature that does not exist yet. Your applicant profile is not included unless you tick the box above.</Notice>
      </div>
      {loading ? <SkeletonCards count={3} label="Preparing passport" /> : error || !opp.data ? (
        <ErrorState error={error ?? new Error("Not found")} onRetry={() => { opp.reload(); report.reload(); history.reload(); }} />
      ) : (
        <PassportDocument opportunity={opp.data} report={report.data} history={history.data ?? []} generatedAt={generatedAt} fit={fit} />
      )}
    </div>
  );
}
