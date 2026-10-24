"use client";

import Link from "next/link";
import { ListChecks } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { OrgAvatar } from "@/components/opportunities/OrgAvatar";
import { EmptyState, SkeletonCards } from "@/components/ui/States";
import { LinkButton } from "@/components/ui/Button";
import { useOpportunityChoices } from "@/features/discovery/useChoices";
import { useSaved } from "@/features/saved/SavedProvider";
import { deadlineLabel } from "@/lib/date-utils";

export function ChecklistIndex() {
  const { choices, loading } = useOpportunityChoices();
  const { isSaved } = useSaved();
  const sorted = [...choices].sort((a, b) => Number(isSaved(b.id)) - Number(isSaved(a.id)));
  return (
    <div className="page">
      <PageHeader eyebrow="Stay organised" title="Application Checklists" subtitle="Step-by-step lists generated from each opportunity's own application instructions." />
      {loading && !choices.length ? <SkeletonCards count={3} /> : sorted.length === 0 ? (
        <EmptyState icon={<ListChecks size={22} />} title="No checklists yet" action={<LinkButton href="/explore" variant="primary">Discover opportunities</LinkButton>}>Save or open an opportunity to generate its checklist.</EmptyState>
      ) : (
        <ul className="saved-list">
          {sorted.map((o) => (
            <li key={o.id} className="saved-item saved-item-simple">
              <OrgAvatar name={o.organization} />
              <div className="saved-main">
                <h2><Link href={`/checklist/${encodeURIComponent(o.id)}`}>{o.title}</Link></h2>
                <p className="muted small">{o.organization} · {o.deadline ? deadlineLabel(o.deadline).text : "Deadline unknown"}{isSaved(o.id) ? " · Saved" : ""}</p>
              </div>
              <LinkButton href={`/checklist/${encodeURIComponent(o.id)}`} size="sm" variant="primary">Open checklist</LinkButton>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
