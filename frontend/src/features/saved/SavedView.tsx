"use client";

import Link from "next/link";
import { Bookmark, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { OrgAvatar } from "@/components/opportunities/OrgAvatar";
import { RecheckButton } from "@/components/opportunities/RecheckButton";
import { Badge } from "@/components/ui/Badge";
import { Button, LinkButton } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { EmptyState, ErrorState, SkeletonCards } from "@/components/ui/States";
import { NoReportBadge, ReportStatusBadge } from "@/components/verification/StatusBadges";
import { useSaved } from "@/features/saved/SavedProvider";
import { deadlineLabel, formatDate, formatDateTime, relativeTime } from "@/lib/date-utils";
import { CATEGORY_LABEL, REPORT_STATUS_SHORT } from "@/lib/formatters";
import type { ReportStatus } from "@/types";

export function SavedView() {
  const { items, savedAt, loading, error, remove, reload } = useSaved();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | ReportStatus | "none">("all");
  const [sort, setSort] = useState<"saved" | "deadline">("saved");

  const list = useMemo(() => {
    const term = q.trim().toLowerCase();
    const filtered = items.filter((o) => {
      if (term && !`${o.title} ${o.organization ?? ""} ${o.tags.join(" ")}`.toLowerCase().includes(term)) return false;
      if (status === "none") return o.verification === null;
      if (status !== "all") return o.verification?.reportStatus === status;
      return true;
    });
    return [...filtered].sort((a, b) =>
      sort === "deadline" ? (a.deadline ? Date.parse(a.deadline) : Infinity) - (b.deadline ? Date.parse(b.deadline) : Infinity) : Date.parse(savedAt[b.id] ?? "") - Date.parse(savedAt[a.id] ?? ""),
    );
  }, [items, q, status, sort, savedAt]);

  return (
    <div className="page">
      <PageHeader eyebrow="Your shortlist" title="Saved Opportunities" subtitle={`${items.length} saved. Recheck them to see whether details have changed.`} />

      {loading ? <SkeletonCards count={3} label="Loading saved opportunities" /> : error ? (
        <ErrorState error={error} onRetry={reload} title="Could not load saved opportunities" />
      ) : items.length === 0 ? (
        <EmptyState icon={<Bookmark size={22} />} title="You haven’t saved anything yet" action={<LinkButton href="/explore" variant="primary">Discover opportunities</LinkButton>}>
          Save opportunities from Discover to keep them here, track deadlines and recheck their claims later.
        </EmptyState>
      ) : (
        <>
          <div className="toolbar" role="search" aria-label="Filter saved opportunities">
            <div className="search-row search-row-sm">
              <label htmlFor="saved-q" className="sr-only">Search saved opportunities</label>
              <input id="saved-q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search saved…" />
            </div>
            <Select
              label="Verification status"
              value={status}
              onChange={(v) => setStatus(v as typeof status)}
              options={[{ value: "all", label: "Any verification status" }, ...(Object.keys(REPORT_STATUS_SHORT) as ReportStatus[]).map((s) => ({ value: s, label: REPORT_STATUS_SHORT[s] })), { value: "none", label: "Not yet verified" }]}
            />
            <Select label="Sort saved" value={sort} onChange={(v) => setSort(v as typeof sort)} options={[{ value: "saved", label: "Recently saved" }, { value: "deadline", label: "Deadline (soonest)" }]} />
          </div>

          {list.length === 0 ? (
            <EmptyState title="No saved opportunities match" action={<Button onClick={() => { setQ(""); setStatus("all"); }}>Clear filters</Button>}>Try a different search or filter.</EmptyState>
          ) : (
            <ul className="saved-list">
              {list.map((o) => {
                const dl = deadlineLabel(o.deadline);
                return (
                  <li key={o.id} className="saved-item">
                    <OrgAvatar name={o.organization} />
                    <div className="saved-main">
                      <h2><Link href={`/opportunities/${encodeURIComponent(o.id)}`}>{o.title}</Link></h2>
                      <p className="muted small">{o.organization ?? "Organisation unknown"} · {CATEGORY_LABEL[o.category]} · {o.location ?? "Location unknown"}</p>
                      <p className={`small deadline-${dl.tone}`}>{o.deadline ? dl.text : o.deadlineText ? `Deadline: ${o.deadlineText}` : "Deadline unknown"}</p>
                    </div>
                    <div className="saved-status">
                      {o.verification ? <ReportStatusBadge status={o.verification.reportStatus} short /> : <NoReportBadge />}
                      <span className="small muted" title={formatDateTime(o.verification?.lastCheckedAt)}>
                        Last rechecked: {o.verification ? relativeTime(o.verification.lastCheckedAt) : "never"}
                      </span>
                      {savedAt[o.id] && <span className="small muted">Saved {formatDate(savedAt[o.id])}</span>}
                      {o.isSample && <Badge tone="purple">Sample</Badge>}
                    </div>
                    <div className="saved-actions">
                      <LinkButton href={`/opportunities/${encodeURIComponent(o.id)}`} size="sm" variant="primary">Open details</LinkButton>
                      <RecheckButton opportunityId={o.id} />
                      <Button size="sm" variant="ghost" icon={<Trash2 size={14} aria-hidden />} onClick={() => remove(o.id)} aria-label={`Remove ${o.title} from saved`}>Remove</Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
