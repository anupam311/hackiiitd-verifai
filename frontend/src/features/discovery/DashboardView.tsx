"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bookmark, Eye, FileCheck2, GitCompareArrows, History, Scale, Search, ShieldAlert, Sparkles, UserRound } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { OrgAvatar } from "@/components/opportunities/OrgAvatar";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ReportStatusBadge } from "@/components/verification/StatusBadges";
import { useNotifications } from "@/features/notifications/useNotifications";
import { useProfile } from "@/features/profile/ProfileProvider";
import { useSaved } from "@/features/saved/SavedProvider";

const FEATURES = [
  { icon: Search, title: "Live discovery", text: "Real-time web retrieval through TinyFish once the backend is configured" },
  { icon: FileCheck2, title: "Claim-level verification", text: "Every claim is checked and shown on its own" },
  { icon: Eye, title: "Source transparency", text: "See where every claim comes from" },
  { icon: ShieldAlert, title: "Conflict detection", text: "Contradictions between sources stay visible" },
  { icon: Bookmark, title: "Save & recheck", text: "Recheck on demand and compare snapshots" },
  { icon: Sparkles, title: "Explainable matching", text: "Eligibility fit with reasons, not guesses" },
];

export function DashboardView() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const saved = useSaved();
  const { profile, hasProfile } = useProfile();
  const { unread } = useNotifications();
  const conflicts = saved.items.filter((o) => o.verification?.reportStatus === "conflicts_detected").length;
  const filled = [profile.educationLevel !== "unknown", profile.fieldOfStudy, profile.institution, profile.graduationYear !== null, profile.location, profile.skills.length, profile.preferredCategories.length].filter(Boolean).length;

  return (
    <div className="page">
      <PageHeader eyebrow="Overview" title="Welcome to VERIFAI" subtitle="Don’t just find it. Verify it." />
      <form className="search-form" role="search" onSubmit={(e) => { e.preventDefault(); router.push(q.trim() ? `/explore?q=${encodeURIComponent(q.trim())}` : "/explore"); }}>
        <div className="search-row">
          <Search size={18} aria-hidden />
          <label htmlFor="dash-q" className="sr-only">Search opportunities</label>
          <input id="dash-q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search opportunities, companies, keywords…" />
          <Button type="submit" variant="primary">Search</Button>
        </div>
      </form>

      <div className="stat-row">
        <div className="stat"><strong>{saved.items.length}</strong><span>Saved opportunities</span></div>
        <div className="stat"><strong>{conflicts}</strong><span>Saved with conflicts</span></div>
        <div className="stat"><strong>{unread}</strong><span>Unread notifications</span></div>
        <div className="stat"><strong>{filled}/7</strong><span>Profile fields filled</span></div>
      </div>

      <div className="grid-4">
        <Card>
          <CardHeader as="h2" title="Saved opportunities" icon={<Bookmark size={17} aria-hidden />} />
          {saved.items.length === 0 ? <p className="muted small">Nothing saved yet.</p> : (
            <ul className="mini-list">
              {saved.items.slice(0, 3).map((o) => (
                <li key={o.id}><OrgAvatar name={o.organization} size={30} /><Link href={`/opportunities/${encodeURIComponent(o.id)}`}>{o.title}</Link>{o.verification && <ReportStatusBadge status={o.verification.reportStatus} short />}</li>
              ))}
            </ul>
          )}
          <Link href="/saved" className="link small">View all saved →</Link>
        </Card>
        <Card>
          <CardHeader as="h2" title="Applicant profile" icon={<UserRound size={17} aria-hidden />} />
          <p className="small">{hasProfile ? `${profile.degree || "Degree not set"}${profile.fieldOfStudy ? `, ${profile.fieldOfStudy}` : ""}` : "No profile yet. Add education, location and interests to see explainable eligibility fit."}</p>
          <Link href="/profile" className="link small">{hasProfile ? "Edit profile →" : "Add profile →"}</Link>
        </Card>
        <Card>
          <CardHeader as="h2" title="Compare sources" icon={<Scale size={17} aria-hidden />} />
          <p className="small muted">Review claim values side by side and spot contradictions.</p>
          <Link href="/compare" className="link small">Compare evidence →</Link>
        </Card>
        <Card>
          <CardHeader as="h2" title="Recheck & history" icon={<History size={17} aria-hidden />} />
          <p className="small muted">Run a recheck and compare it with earlier snapshots.</p>
          <div className="row-links"><Link href="/recheck" className="link small">Recheck →</Link><Link href="/history" className="link small">History →</Link></div>
        </Card>
      </div>

      <section className="feature-strip" aria-label="What VERIFAI does">
        {FEATURES.map(({ icon: Icon, title, text }) => (
          <div key={title}><Icon size={22} aria-hidden /><strong>{title}</strong><small>{text}</small></div>
        ))}
      </section>
      <p className="muted small"><GitCompareArrows size={13} aria-hidden /> Features depend on the backend integrations that are configured. Anything shown from sample data is labelled as such.</p>
    </div>
  );
}
