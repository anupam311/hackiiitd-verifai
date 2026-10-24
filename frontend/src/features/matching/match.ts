import type { ApplicantProfile, EligibilityAnalysis, EligibilityRequirement, FitLevel, MatchReason, Opportunity } from "@/types";
import { EDUCATION_LABEL } from "@/lib/formatters";

export const FIT_LABEL: Record<FitLevel, string> = {
  strong: "Strong fit",
  partial: "Possible fit",
  weak: "Unlikely fit",
  insufficient: "Fit unknown",
};

const norm = (s: string) => s.trim().toLowerCase();

export const EMPTY_PROFILE: ApplicantProfile = {
  educationLevel: "unknown",
  degree: "",
  fieldOfStudy: "",
  institution: "",
  graduationYear: null,
  location: "",
  preferredRegions: [],
  experience: "",
  skills: [],
  researchInterests: [],
  preferredCategories: [],
  workModePreference: "any",
};

export function isProfileUsable(p: ApplicantProfile | null): p is ApplicantProfile {
  if (!p) return false;
  return p.educationLevel !== "unknown" || p.fieldOfStudy.trim() !== "" || p.graduationYear !== null || p.location.trim() !== "";
}

function evaluate(req: EligibilityRequirement, p: ApplicantProfile): MatchReason {
  const base = { requirementId: req.id, requirement: req.text };
  switch (req.kind) {
    case "education_level": {
      if (!req.values?.length) return { ...base, outcome: "unknown", reasoning: "The source does not state which education levels qualify." };
      if (p.educationLevel === "unknown") return { ...base, outcome: "unknown", reasoning: "Add your education level to your profile to evaluate this." };
      const ok = req.values.some((v) => norm(v) === "any" || norm(v) === p.educationLevel);
      return ok
        ? { ...base, outcome: "match", reasoning: `Your profile lists ${EDUCATION_LABEL[p.educationLevel].toLowerCase()} study, which is accepted.` }
        : { ...base, outcome: "mismatch", reasoning: `Your profile lists ${EDUCATION_LABEL[p.educationLevel].toLowerCase()} study; the requirement is ${req.values.join(", ")}.` };
    }
    case "field_of_study": {
      if (!req.values?.length) return { ...base, outcome: "unknown", reasoning: "The source does not name specific fields." };
      if (!p.fieldOfStudy.trim()) return { ...base, outcome: "unknown", reasoning: "Add your field of study to your profile to evaluate this." };
      const field = norm(p.fieldOfStudy);
      const ok = req.values.some((v) => norm(v) === "any" || field.includes(norm(v)) || norm(v).includes(field));
      return ok
        ? { ...base, outcome: "match", reasoning: `“${p.fieldOfStudy}” appears in the accepted fields.` }
        : { ...base, outcome: "mismatch", reasoning: `“${p.fieldOfStudy}” is not in the listed fields (${req.values.join(", ")}). “Related fields” may still be accepted — check the source.` };
    }
    case "graduation_year": {
      if (p.graduationYear === null) return { ...base, outcome: "unknown", reasoning: "Add your graduation year to your profile to evaluate this." };
      const lo = req.minYear ?? -Infinity;
      const hi = req.maxYear ?? Infinity;
      return p.graduationYear >= lo && p.graduationYear <= hi
        ? { ...base, outcome: "match", reasoning: `Your graduation year (${p.graduationYear}) is within range.` }
        : { ...base, outcome: "mismatch", reasoning: `Your graduation year (${p.graduationYear}) is outside ${req.minYear ?? "…"}–${req.maxYear ?? "…"}.` };
    }
    case "location": {
      if (!req.values?.length) return { ...base, outcome: "unknown", reasoning: "The source does not state a location requirement." };
      const mine = [p.location, ...p.preferredRegions].map(norm).filter(Boolean);
      if (mine.length === 0) return { ...base, outcome: "unknown", reasoning: "Add your location to your profile to evaluate this." };
      const ok = req.values.some((v) => mine.some((m) => m.includes(norm(v)) || norm(v).includes(m)));
      return ok ? { ...base, outcome: "match", reasoning: "Your location or preferred regions overlap." } : { ...base, outcome: "mismatch", reasoning: "Your location does not overlap with the stated region." };
    }
    case "skill": {
      if (!req.values?.length) return { ...base, outcome: "unknown", reasoning: "No specific skills were extracted." };
      const mine = p.skills.map(norm);
      const ok = req.values.every((v) => mine.includes(norm(v)));
      return ok ? { ...base, outcome: "match", reasoning: "All listed skills are in your profile." } : { ...base, outcome: "unknown", reasoning: "Not all skills are listed in your profile. A missing skill is not treated as a mismatch." };
    }
    default:
      return { ...base, outcome: "unknown", reasoning: "VERIFAI cannot evaluate this requirement automatically. It is not treated as satisfied — check the source." };
  }
}

/**
 * Eligibility analysis. Unknown requirements are never counted as satisfied,
 * and this result is independent of verification status or evidence quality.
 */
export function analyzeEligibility(opp: Pick<Opportunity, "eligibility">, profile: ApplicantProfile | null): EligibilityAnalysis {
  const counts = { match: 0, mismatch: 0, unknown: 0 };
  if (!isProfileUsable(profile) || opp.eligibility.length === 0) {
    const reasons: MatchReason[] = opp.eligibility.map((r) => ({
      requirementId: r.id,
      requirement: r.text,
      outcome: "unknown",
      reasoning: isProfileUsable(profile) ? "No evaluation possible." : "Complete your applicant profile to evaluate this requirement.",
    }));
    counts.unknown = reasons.length;
    return { reasons, fit: "insufficient", counts, profileIncomplete: !isProfileUsable(profile) };
  }
  const reasons = opp.eligibility.map((r) => evaluate(r, profile));
  for (const r of reasons) counts[r.outcome] += 1;
  let fit: FitLevel;
  if (counts.match === 0 && counts.mismatch === 0) fit = "insufficient";
  else if (counts.mismatch > 0 && counts.match === 0) fit = "weak";
  else if (counts.mismatch > 0) fit = "partial";
  else if (counts.unknown === 0) fit = "strong";
  else fit = "partial";
  return { reasons, fit, counts, profileIncomplete: false };
}
