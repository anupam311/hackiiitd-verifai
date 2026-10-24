"use client";

import Link from "next/link";
import type { Opportunity } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { analyzeEligibility, FIT_LABEL } from "@/features/matching/match";
import { useProfile } from "@/features/profile/ProfileProvider";

/**
 * Qualitative, explainable eligibility fit computed from the applicant profile.
 * It says nothing about authenticity or evidence quality, and has no percentage.
 */
export function MatchBadge({ opportunity }: { opportunity: Opportunity }) {
  const { profile, hasProfile } = useProfile();
  const analysis = analyzeEligibility(opportunity, hasProfile ? profile : null);
  const { match, mismatch, unknown } = analysis.counts;

  if (analysis.profileIncomplete) {
    return (
      <div className="fit">
        <span className="fit-label">Your fit</span>
        <Badge tone="gray">Fit unknown</Badge>
        <Link href="/profile" className="link small">
          Add your profile
        </Link>
      </div>
    );
  }
  const tone = analysis.fit === "strong" ? "purple" : analysis.fit === "partial" ? "blue" : "gray";
  return (
    <div className="fit">
      <span className="fit-label">Your fit</span>
      <Badge tone={tone} title="Eligibility fit from your profile. Unknown requirements are not treated as satisfied.">
        {FIT_LABEL[analysis.fit]}
      </Badge>
      <span className="fit-counts small muted">
        {match} match · {mismatch} no match · {unknown} unknown
      </span>
    </div>
  );
}
