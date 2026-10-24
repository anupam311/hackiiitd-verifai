"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ClipboardList, ExternalLink as ExtIcon, FileBadge2 } from "lucide-react";
import { useMemo } from "react";
import type { ClaimType, Opportunity, VerificationReport } from "@/types";
import { ConflictBanner } from "@/components/comparison/ConflictBanner";
import { SourceComparisonTable } from "@/components/comparison/SourceComparisonTable";
import { SourceCard } from "@/components/evidence/SourceCard";
import { EligibilityAnalysisView } from "@/components/profile/EligibilityAnalysisView";
import { Badge } from "@/components/ui/Badge";
import { ExternalLink, LinkButton } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorState, Notice, SkeletonCards } from "@/components/ui/States";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { ClaimTable } from "@/components/verification/ClaimTable";
import { CoverageSummary } from "@/components/verification/CoverageSummary";
import { ReportView } from "@/components/verification/ReportView";
import { ClaimStatusBadge, NoReportBadge, ReportStatusBadge } from "@/components/verification/StatusBadges";
import { buildComparison } from "@/features/verification/compare";
import { getOpportunity, listOpportunities } from "@/features/discovery/api";
import { analyzeEligibility } from "@/features/matching/match";
import { useProfile } from "@/features/profile/ProfileProvider";
import { getReport, getSources } from "@/features/verification/api";
import { useAsync } from "@/hooks/useAsync";
import { ApiError } from "@/lib/api-errors";
import { deadlineLabel, formatDate, formatDateTime } from "@/lib/date-utils";
import { CATEGORY_LABEL, CLAIM_TYPE_LABEL, WORK_MODE_LABEL } from "@/lib/formatters";
import { countClaims, deriveReportStatus } from "@/lib/verification";
import { useDemo } from "@/providers/DemoProvider";
import { OpportunityCard } from "./OpportunityCard";
import { OrgAvatar } from "./OrgAvatar";
import { RecheckButton } from "./RecheckButton";
import { SaveButton } from "./SaveButton";

const TAB_IDS = ["overview", "report", "sources", "similar"] as const;
type TabId = (typeof TAB_IDS)[number];

const STATE_LABEL = { open: "Listed as open", closed: "Listed as closed", rolling: "Rolling applications", unknown: "Application status unknown" } as const;

function listedValue(o: Opportunity, type: ClaimType): { text: string; muted: boolean; href?: string } {
  const unknown = (t: string) => ({ text: t, muted: true });
  switch (type) {
    case "deadline":
      return o.deadline ? { text: formatDate(o.deadline), muted: false } : o.deadlineText ? { text: o.deadlineText, muted: false } : unknown("Unknown — no deadline found");
    case "application_status":
      return { text: STATE_LABEL[o.applicationState], muted: o.applicationState === "unknown" };
    case "application_url":
      return o.applicationUrl ? { text: o.applicationUrl.replace(/^https?:\/\//, ""), muted: false, href: o.applicationUrl } : unknown("No application link found");
    case "eligibility":
      return o.eligibilitySummary ? { text: o.eligibilitySummary, muted: false } : unknown("Not stated");
    case "stipend":
      return o.stipendText ? { text: o.stipendText, muted: false } : unknown("Not stated");
    case "location":
      return o.location ? { text: o.location, muted: false } : unknown("Unknown");
    case "duration":
      return o.durationText ? { text: o.durationText, muted: false } : unknown("Not stated");
    default:
      return unknown("—");
  }
}

const KEY_ROWS: ClaimType[] = ["deadline", "application_status", "application_url", "eligibility", "stipend", "location", "duration"];

export function OpportunityDetail({ id }: { id: string }) {
  const { demo, ready } = useDemo();
  const router = useRouter();
  const params = useSearchParams();
  const tabParam = params.get("tab");
  const tab: TabId = (TAB_IDS as readonly string[]).includes(tabParam ?? "") ? (tabParam as TabId) : "overview";
  const setTab = (t: string) => router.replace(`/opportunities/${encodeURIComponent(id)}?tab=${t}`, { scroll: false });

  const opp = useAsync((s) => getOpportunity(demo, id, s), [demo, id], ready);
  const report = useAsync(async (s) => {
    try {
      return await getReport(demo, id, s);
    } catch (e) {
      // 404/405/501 simply mean no report exists (yet); anything else is a real error.
      if (e instanceof ApiError && e.kind === "not_implemented") return null;
      throw e;
    }
  }, [demo, id], ready);
  const sources = useAsync((s) => getSources(demo, id, s), [demo, id], ready && tab === "sources");
  const similar = useAsync((s) => listOpportunities(demo, s), [demo], ready && tab === "similar");
  const { profile, hasProfile } = useProfile();

  const o = opp.data;
  const r: VerificationReport | null = report.data;
  const analysis = useMemo(() => (o ? analyzeEligibility(o, hasProfile ? profile : null) : null), [o, profile, hasProfile]);
  const comparison = useMemo(() => (r ? buildComparison(r) : null), [r]);

  if (opp.loading || !ready) return <div className="page"><SkeletonCards count={2} label="Loading opportunity" /></div>;
  if (opp.error || !o) {
    const notFound = opp.error instanceof ApiError && opp.error.kind === "not_implemented";
    return (
      <div className="page">
        <Link href="/explore" className="back-link"><ArrowLeft size={15} aria-hidden /> Back to results</Link>
        {notFound ? (
          <EmptyState title="Opportunity not found" action={<LinkButton href="/explore" variant="primary">Back to Discover</LinkButton>}>
            This opportunity does not exist in the {demo ? "sample data" : "backend"}.
          </EmptyState>
        ) : (
          <ErrorState error={opp.error} onRetry={opp.reload} title="Could not load this opportunity" />
        )}
      </div>
    );
  }

  const dl = deadlineLabel(o.deadline);
  const status = r ? deriveReportStatus(r.claims) : null;
  const counts = r ? countClaims(r.claims) : null;
  const claimOf = (t: ClaimType) => r?.claims.find((c) => c.type === t);
  const similarList = (similar.data?.opportunities ?? []).filter((x) => x.id !== o.id && (x.category === o.category || x.tags.some((t) => o.tags.includes(t)))).slice(0, 3);

  return (
    <div className="page">
      <Link href="/explore" className="back-link"><ArrowLeft size={15} aria-hidden /> Back to results</Link>

      <header className="detail-head card card-pad">
        <OrgAvatar name={o.organization} size={56} />
        <div className="detail-title">
          <h1>{o.title}</h1>
          <p className="muted">
            {o.organization ?? "Organisation unknown"} · {CATEGORY_LABEL[o.category]} · {o.location ?? "Location unknown"}
            {o.workMode !== "unknown" ? ` · ${WORK_MODE_LABEL[o.workMode]}` : ""}
          </p>
          <div className="badge-row">
            {o.isSample && <Badge tone="purple">Sample data</Badge>}
            <Badge tone="blue">{STATE_LABEL[o.applicationState]}</Badge>
            <Badge tone={dl.tone === "soon" ? "amber" : "gray"}>{o.deadline ? dl.text : o.deadlineText ? `Deadline: ${o.deadlineText}` : "Deadline unknown"}</Badge>
            {status ? <ReportStatusBadge status={status} /> : <NoReportBadge />}
          </div>
        </div>
        <div className="detail-actions">
          <SaveButton opportunity={o} size="md" />
          <RecheckButton opportunityId={o.id} size="md" variant="primary" label="Recheck now" />
        </div>
        <div className="detail-links">
          {o.canonicalUrl && <ExternalLink href={o.canonicalUrl}><ExtIcon size={13} aria-hidden /> Original source</ExternalLink>}
          {o.applicationUrl && <ExternalLink href={o.applicationUrl}><ExtIcon size={13} aria-hidden /> Application page</ExternalLink>}
          <Link className="link" href={`/checklist/${encodeURIComponent(o.id)}`}><ClipboardList size={13} aria-hidden /> Application checklist</Link>
          <Link className="link" href={`/passport/${encodeURIComponent(o.id)}`}><FileBadge2 size={13} aria-hidden /> Verification Passport</Link>
          <Link className="link" href={`/history?opp=${encodeURIComponent(o.id)}`}>History</Link>
        </div>
      </header>

      <Tabs
        label="Opportunity sections"
        idPrefix="opp"
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "report", label: "Verification Report" },
          { id: "sources", label: "Sources", badge: r ? <span className="tab-count">{r.sources.length}</span> : null },
          { id: "similar", label: "Similar Opportunities" },
        ]}
      />

      <TabPanel id="overview" active={tab} idPrefix="opp">
        <div className="grid-overview">
          <div className="stack">
            <Card>
              <CardHeader title="Verification summary" />
              {report.loading ? <p className="muted">Loading report…</p> : report.error ? <ErrorState error={report.error} onRetry={report.reload} title="Could not load the verification report" /> : r && counts && status ? (
                <>
                  <div className="summary-status"><ReportStatusBadge status={status} /><span className="small muted">Generated {formatDateTime(r.generatedAt)}</span></div>
                  <CoverageSummary counts={counts} />
                </>
              ) : (
                <Notice tone="info" title="Not yet verified">No verification report exists for this opportunity. Run a recheck to retrieve sources and check claims. Nothing here is verified yet.</Notice>
              )}
            </Card>

            <Card>
              <CardHeader title="Key information" />
              <div className="table-wrap">
                <table className="table keyinfo">
                  <caption className="sr-only">Listed values and their verification status</caption>
                  <thead>
                    <tr><th scope="col">Detail</th><th scope="col">Listed value (extracted)</th><th scope="col">Verification</th></tr>
                  </thead>
                  <tbody>
                    {KEY_ROWS.map((t) => {
                      const v = listedValue(o, t);
                      const c = claimOf(t);
                      return (
                        <tr key={t}>
                          <th scope="row" data-label="Detail">{CLAIM_TYPE_LABEL[t]}</th>
                          <td data-label="Listed value">{v.href ? <ExternalLink href={v.href}>{v.text}</ExternalLink> : <span className={v.muted ? "muted" : ""}>{v.text}</span>}</td>
                          <td data-label="Verification">{c ? <ClaimStatusBadge status={c.status} /> : <Badge tone="gray">Not checked</Badge>}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="small muted">Listed values were extracted from sources. Only the verification badge reflects whether evidence supports the value.</p>
            </Card>
          </div>

          <div className="stack">
            {comparison && <ConflictBanner comparison={comparison} action={<button className="link-btn" onClick={() => setTab("sources")}>View sources</button>} />}
            <Card>
              <CardHeader title="Claim verification" action={r ? <button className="link-btn" onClick={() => setTab("report")}>Evidence & details →</button> : undefined} />
              {r ? <ClaimTable claims={r.claims} sources={r.sources} compact /> : <p className="muted">No claims have been checked, so no claim is marked confirmed.</p>}
            </Card>
            {analysis && (
              <Card>
                <CardHeader title="Your eligibility fit" />
                <EligibilityAnalysisView analysis={analysis} />
              </Card>
            )}
            {r && r.sources.length > 0 && (
              <Card>
                <CardHeader title={`Sources (${r.sources.length})`} action={<button className="link-btn" onClick={() => setTab("sources")}>Compare sources →</button>} />
                <div className="source-grid source-grid-compact">{r.sources.map((s) => <SourceCard key={s.id} source={s} />)}</div>
              </Card>
            )}
          </div>
        </div>
      </TabPanel>

      <TabPanel id="report" active={tab} idPrefix="opp">
        {report.loading ? <SkeletonCards count={2} /> : report.error ? <ErrorState error={report.error} onRetry={report.reload} /> : r ? (
          <ReportView report={r} actions={<LinkButton href={`/reports/${encodeURIComponent(o.id)}`} size="sm">Open full report</LinkButton>} />
        ) : (
          <EmptyState title="No verification report yet" action={<RecheckButton opportunityId={o.id} size="md" variant="primary" label="Run a recheck" />}>
            Verification starts when sources are retrieved and claims are checked. Until then, no value for this opportunity is verified.
          </EmptyState>
        )}
      </TabPanel>

      <TabPanel id="sources" active={tab} idPrefix="opp">
        {sources.loading ? <SkeletonCards count={2} /> : sources.error ? <ErrorState error={sources.error} onRetry={sources.reload} /> : sources.data ? (
          <div className="stack">
            <ConflictBanner comparison={sources.data} />
            <Card><CardHeader title="Source comparison" /><SourceComparisonTable comparison={sources.data} /></Card>
            <div className="source-grid">{sources.data.sources.map((s) => <SourceCard key={s.id} source={s} />)}</div>
            <p className="small"><Link className="link" href={`/compare?opp=${encodeURIComponent(o.id)}`}>Open in Compare Sources →</Link></p>
          </div>
        ) : null}
      </TabPanel>

      <TabPanel id="similar" active={tab} idPrefix="opp">
        <Notice tone="info" title="How similarity works">Similar opportunities share a category or tags with this one. Similarity says nothing about verification status.</Notice>
        {similar.loading ? <SkeletonCards count={2} /> : similar.error ? <ErrorState error={similar.error} onRetry={similar.reload} /> : similarList.length === 0 ? (
          <EmptyState title="No similar opportunities found">There are no other stored opportunities sharing this category or tags.</EmptyState>
        ) : (
          <div className="opp-list">{similarList.map((x) => <OpportunityCard key={x.id} opportunity={x} />)}</div>
        )}
      </TabPanel>
    </div>
  );
}
