import type { ApplicantProfile } from "@/types";

export type ProfileErrors = Partial<Record<keyof ApplicantProfile, string>>;

const MAX = 200;

export function validateProfile(p: ApplicantProfile): ProfileErrors {
  const e: ProfileErrors = {};
  for (const k of ["degree", "fieldOfStudy", "institution", "location"] as const) {
    if (p[k].length > MAX) e[k] = `Keep this under ${MAX} characters.`;
  }
  if (p.experience.length > 1000) e.experience = "Keep this under 1,000 characters.";
  if (p.graduationYear !== null) {
    const y = p.graduationYear;
    if (!Number.isInteger(y) || y < 1990 || y > 2100) e.graduationYear = "Enter a four-digit year between 1990 and 2100.";
  }
  for (const k of ["skills", "researchInterests", "preferredRegions"] as const) {
    if (p[k].length > 30) e[k] = "Add at most 30 items.";
    else if (p[k].some((x) => x.length > 60)) e[k] = "Each item must be under 60 characters.";
  }
  return e;
}

export const splitList = (s: string): string[] => [...new Set(s.split(",").map((x) => x.trim()).filter(Boolean))];
