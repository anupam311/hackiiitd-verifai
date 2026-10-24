"use client";

import { ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EligibilityAnalysisView } from "@/components/profile/EligibilityAnalysisView";
import { OpportunityPicker } from "@/components/opportunities/OpportunityPicker";
import { ProfileForm } from "@/components/profile/ProfileForm";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState, Notice } from "@/components/ui/States";
import { useOpportunityChoices } from "@/features/discovery/useChoices";
import { analyzeEligibility } from "@/features/matching/match";
import { useDemo } from "@/providers/DemoProvider";
import { useToast } from "@/providers/ToastProvider";
import { useProfile } from "./ProfileProvider";

export function ProfileView() {
  const { profile, hasProfile, save, clear } = useProfile();
  const { demo } = useDemo();
  const toast = useToast();
  const { choices } = useOpportunityChoices();
  const [oppId, setOppId] = useState("");
  const opp = choices.find((o) => o.id === oppId) ?? choices[0] ?? null;
  const analysis = useMemo(() => (opp ? analyzeEligibility(opp, hasProfile ? profile : null) : null), [opp, profile, hasProfile]);

  return (
    <div className="page">
      <PageHeader eyebrow="Applicant profile" title="Applicant Profile" subtitle="Used only to explain how well an opportunity's listed requirements fit you. It never changes verification results." />
      {demo && <Notice tone="info" title="Sample profile">This profile is invented sample data. Edits stay in this browser only.</Notice>}
      <div className="grid-profile">
        <Card>
          <CardHeader title="Your details" />
          <p className="privacy-note"><ShieldCheck size={15} aria-hidden /> We only ask for what matching needs. No ID numbers, street address, date of birth or financial details are collected.</p>
          <ProfileForm
            profile={profile}
            onClear={() => { clear(); toast({ tone: "info", title: "Profile cleared" }); }}
            onSave={async (p) => {
              const { synced } = await save(p);
              toast({ tone: "success", title: "Profile saved", body: synced ? "Saved to your account." : "Saved in this browser. It is not synced to a server." });
            }}
          />
        </Card>
        <Card>
          <CardHeader title="Eligibility analysis" />
          {choices.length === 0 ? (
            <EmptyState title="No opportunities to analyse">Discover or save an opportunity, then return to see how its requirements fit your profile.</EmptyState>
          ) : (
            <>
              <OpportunityPicker choices={choices} value={opp?.id ?? ""} onChange={setOppId} label="Analyse fit for" />
              {analysis && <EligibilityAnalysisView analysis={analysis} />}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
