
"use client";

import Link from "next/link";
import {
  CalendarClock,
  ChevronRight,
  MapPin,
  ExternalLink,
} from "lucide-react";

import type { Opportunity } from "@/types";
import { Badge } from "@/components/ui/Badge";
import {
  NoReportBadge,
  ReportStatusBadge,
} from "@/components/verification/StatusBadges";
import { useCompare } from "@/features/comparison/CompareProvider";
import { deadlineLabel, relativeTime } from "@/lib/date-utils";
import { CATEGORY_LABEL, WORK_MODE_LABEL } from "@/lib/formatters";
import { MatchBadge } from "./MatchBadge";
import { OrgAvatar } from "./OrgAvatar";
import { RecheckButton } from "./RecheckButton";
import { SaveButton } from "./SaveButton";

function isValidApplicationUrl(url: string | null): boolean {
  if (!url) return false;

  try {
    const parsedUrl = new URL(url);
    return (
      parsedUrl.protocol === "https:" ||
      parsedUrl.protocol === "http:"
    );
  } catch {
    return false;
  }
}

export function OpportunityCard({
  opportunity: o,
  selected = false,
}: {
  opportunity: Opportunity;
  selected?: boolean;
}) {
  const { isSelected, toggle } = useCompare();
  const dl = deadlineLabel(o.deadline);
  const picked = isSelected(o.id);
  const titleId = `opp-${o.id}-title`;
  const hasApplicationUrl = isValidApplicationUrl(o.applicationUrl);

  return (
    <article
      className={`opp-card ${selected ? "opp-selected" : ""}`}
      aria-labelledby={titleId}
    >
      <OrgAvatar name={o.organization} />

      <div className="opp-main">
        <div className="opp-title-row">
          <h3 id={titleId}>
            <Link href={`/opportunities/${encodeURIComponent(o.id)}`}>
              {o.title}
            </Link>
          </h3>

          {o.isSample && <Badge tone="purple">Sample</Badge>}
        </div>

        <p className="opp-meta">
          {o.organization ?? "Organisation unknown"} ·{" "}
          {CATEGORY_LABEL[o.category]} ·{" "}
          <span className="opp-loc">
            <MapPin size={12} aria-hidden="true" />
            {o.location ?? "Location unknown"}
          </span>
          {o.workMode !== "unknown" && (
            <> · {WORK_MODE_LABEL[o.workMode]}</>
          )}
        </p>

        <p className={`opp-deadline deadline-${dl.tone}`}>
          <CalendarClock size={13} aria-hidden="true" />{" "}
          {o.deadline
            ? dl.text
            : o.deadlineText
              ? `Deadline: ${o.deadlineText}`
              : dl.text}
        </p>

        <p className="opp-desc">{o.description}</p>

        {o.eligibilitySummary && (
          <p className="opp-elig small">
            <span>Eligibility (as listed):</span>{" "}
            {o.eligibilitySummary}
          </p>
        )}

        <ul className="tags" aria-label="Tags">
          {o.tags.map((tag) => (
            <li key={tag}>{tag}</li>
          ))}
        </ul>

        <div className="opp-actions">
          <SaveButton opportunity={o} />
          <RecheckButton opportunityId={o.id} />

          <label className="check-inline">
            <input
              type="checkbox"
              checked={picked}
              onChange={() => toggle(o)}
            />
            <span>Compare</span>
          </label>
        </div>
      </div>

      <div className="opp-side">
        <MatchBadge opportunity={o} />

        <div className="opp-verif">
          <span className="fit-label">Verification</span>

          {o.verification ? (
            <ReportStatusBadge
              status={o.verification.reportStatus}
              short
            />
          ) : (
            <NoReportBadge />
          )}

          <span className="small muted">
            {o.verification
              ? `Checked ${relativeTime(o.verification.lastCheckedAt)}`
              : "No report yet"}
          </span>
        </div>

        <div className="opp-card-actions">
          {hasApplicationUrl && !o.isSample ? (
            <a
              className="btn btn-primary btn-sm"
              href={o.applicationUrl!}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Apply for ${o.title} on the application website`}
            >
              Apply Now <ExternalLink size={14} aria-hidden="true" />
            </a>
          ) : (
            <button
              className="btn btn-primary btn-sm"
              type="button"
              disabled
              title={
                o.isSample
                  ? "Sample opportunity: application link is not available in the demo."
                  : "No valid application URL is available."
              }
            >
              Application link unavailable
            </button>
          )}

          <Link
            className="btn btn-primary btn-sm"
            href={`/opportunities/${encodeURIComponent(o.id)}`}
            aria-label={`View details: ${o.title}`}
          >
            View details <ChevronRight size={14} aria-hidden="true" />
          </Link>
        </div>
      </div>
    </article>
  );
}
