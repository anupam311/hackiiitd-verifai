"use client";

import Link from "next/link";
import { CalendarClock, ChevronRight, MapPin } from "lucide-react";
import type { Opportunity } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { NoReportBadge, ReportStatusBadge } from "@/components/verification/StatusBadges";
import { useCompare } from "@/features/comparison/CompareProvider";
import { deadlineLabel, relativeTime } from "@/lib/date-utils";
import { CATEGORY_LABEL, WORK_MODE_LABEL } from "@/lib/formatters";
import { MatchBadge } from "./MatchBadge";
import { OrgAvatar } from "./OrgAvatar";
import { RecheckButton } from "./RecheckButton";
import { SaveButton } from "./SaveButton";

export function OpportunityCard({ opportunity: o, selected = false }: { opportunity: Opportunity; selected?: boolean }) {
  const { isSelected, toggle } = useCompare();
  const dl = deadlineLabel(o.deadline);
  const picked = isSelected(o.id);
  const titleId = `opp-${o.id}-title`;

  return (
    <article className={`opp-card ${selected ? "opp-selected" : ""}`} aria-labelledby={titleId}>
      <OrgAvatar name={o.organization} />
      <div className="opp-main">
        <div className="opp-title-row">
          <h3 id={titleId}>
            <Link href={`/opportunities/${encodeURIComponent(o.id)}`}>{o.title}</Link>
          </h3>
          {o.isSample && <Badge tone="purple">Sample</Badge>}
        </div>
        <p className="opp-meta">
          {o.organization ?? "Organisation unknown"} · {CATEGORY_LABEL[o.category]} ·{" "}
          <span className="opp-loc">
            <MapPin size={12} aria-hidden /> {o.location ?? "Location unknown"}
          </span>
          {o.workMode !== "unknown" && <> · {WORK_MODE_LABEL[o.workMode]}</>}
        </p>
        <p className={`opp-deadline deadline-${dl.tone}`}>
          <CalendarClock size={13} aria-hidden /> {o.deadline ? dl.text : o.deadlineText ? `Deadline: ${o.deadlineText}` : dl.text}
        </p>
        <p className="opp-desc">{o.description}</p>
        {o.eligibilitySummary && (
          <p className="opp-elig small">
            <span>Eligibility (as listed):</span> {o.eligibilitySummary}
          </p>
        )}
        <ul className="tags" aria-label="Tags">
          {o.tags.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
        <div className="opp-actions">
          <SaveButton opportunity={o} />
          <RecheckButton opportunityId={o.id} />
          <label className="check-inline">
            <input type="checkbox" checked={picked} onChange={() => toggle(o)} />
            <span>Compare</span>
          </label>
        </div>
      </div>
      <div className="opp-side">
        <MatchBadge opportunity={o} />
        <div className="opp-verif">
          <span className="fit-label">Verification</span>
          {o.verification ? <ReportStatusBadge status={o.verification.reportStatus} short /> : <NoReportBadge />}
          <span className="small muted">{o.verification ? `Checked ${relativeTime(o.verification.lastCheckedAt)}` : "No report yet"}</span>
        </div>
        <Link className="btn btn-primary btn-sm" href={`/opportunities/${encodeURIComponent(o.id)}`} aria-label={`View details: ${o.title}`}>
          View details <ChevronRight size={14} aria-hidden />
        </Link>
      </div>
    </article>
  );
}
