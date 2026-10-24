"use client";

import Link from "next/link";
import { AlertTriangle, Bell, CalendarClock, CheckCheck, RefreshCw, ShieldAlert, Bookmark } from "lucide-react";
import { useState } from "react";
import type { NotificationKind } from "@/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { EmptyState, ErrorState, Notice, SkeletonCards } from "@/components/ui/States";
import { ApiError } from "@/lib/api-errors";
import { formatDateTime } from "@/lib/date-utils";
import { useDemo } from "@/providers/DemoProvider";
import { useNotifications } from "./useNotifications";

const KIND: Record<NotificationKind, { label: string; icon: typeof Bell }> = {
  recheck_result: { label: "Recheck result", icon: RefreshCw },
  deadline_changed: { label: "Deadline changed", icon: CalendarClock },
  conflict_detected: { label: "New conflict", icon: ShieldAlert },
  saved_update: { label: "Saved update", icon: Bookmark },
  verification_failed: { label: "Verification failed", icon: AlertTriangle },
};

export function NotificationsView() {
  const { demo } = useDemo();
  const { items, unread, loading, error, reload, markRead, markAllRead } = useNotifications();
  const [kind, setKind] = useState("all");
  const list = items.filter((n) => kind === "all" || n.kind === kind);
  const unavailable = error instanceof ApiError && error.kind === "not_implemented";

  return (
    <div className="page">
      <PageHeader
        eyebrow="Updates"
        title="Notifications"
        subtitle="Results of rechecks you ran and changes between runs."
        actions={<Button icon={<CheckCheck size={15} aria-hidden />} onClick={markAllRead} disabled={unread === 0}>Mark all read</Button>}
      />
      {demo && <Notice tone="info" title="Sample notifications">These are invented previews. No monitoring service is running, and nothing here arrived from a live system.</Notice>}
      {loading ? <SkeletonCards count={3} /> : unavailable ? (
        <EmptyState icon={<Bell size={22} />} title="Notifications aren’t available yet">The backend doesn’t provide a notifications endpoint, and VERIFAI is not monitoring opportunities in the background. Results of rechecks you run appear in History.</EmptyState>
      ) : error ? <ErrorState error={error} onRetry={reload} /> : (
        <>
          <div className="toolbar">
            <Select label="Type" hideLabel={false} value={kind} onChange={setKind} options={[{ value: "all", label: "All types" }, ...Object.entries(KIND).map(([value, k]) => ({ value, label: k.label }))]} />
            <p className="muted small" role="status">{unread} unread</p>
          </div>
          {list.length === 0 ? <EmptyState title="No notifications">Nothing to show for this filter.</EmptyState> : (
            <ul className="notif-list">
              {list.map((n) => {
                const Icon = KIND[n.kind].icon;
                return (
                  <li key={n.id} className={n.read ? "" : "notif-unread"}>
                    <span className={`notif-icon notif-${n.kind}`} aria-hidden><Icon size={17} /></span>
                    <div className="notif-body">
                      <div className="badge-row"><strong>{n.title}</strong>{!n.read && <Badge tone="purple">New</Badge>}{n.isSample && <Badge tone="gray">Sample</Badge>}</div>
                      <p className="small">{n.body}</p>
                      <p className="small muted">{KIND[n.kind].label} · {formatDateTime(n.createdAt)}</p>
                    </div>
                    <div className="notif-actions">
                      {n.opportunityId && <Link className="btn btn-secondary btn-sm" href={`/opportunities/${encodeURIComponent(n.opportunityId)}`} onClick={() => markRead(n.id)}>Open</Link>}
                      {!n.read && <Button size="sm" variant="ghost" onClick={() => markRead(n.id)}>Mark read</Button>}
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
