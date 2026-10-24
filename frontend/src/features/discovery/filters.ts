import type { Opportunity, OpportunityCategory } from "@/types";
import { coverageScore } from "@/lib/verification";
import { daysUntil } from "@/lib/date-utils";

export type SortKey = "relevance" | "deadline" | "completeness";

export interface FilterState {
  query: string;
  category: OpportunityCategory | "all";
  location: string; // "all" | free text from options
  field: string; // "all" | field label
  deadline: "any" | "30" | "60" | "90" | "none";
  level: string; // "all" | EducationLevel
  workMode: "all" | "remote" | "on_site" | "hybrid";
  organization: string; // "all" | org
  status: "all" | "open" | "rolling" | "unknown";
  sort: SortKey;
}

export const DEFAULT_FILTERS: FilterState = {
  query: "",
  category: "all",
  location: "all",
  field: "all",
  deadline: "any",
  level: "all",
  workMode: "all",
  organization: "all",
  status: "all",
  sort: "relevance",
};

export function activeFilterCount(f: FilterState): number {
  return (Object.keys(DEFAULT_FILTERS) as (keyof FilterState)[]).filter((k) => k !== "query" && k !== "sort" && f[k] !== DEFAULT_FILTERS[k]).length;
}

const tokens = (s: string) => s.toLowerCase().split(/[^a-z0-9₹]+/).filter((t) => t.length > 1);

/** Keyword overlap — a sort aid only. This is NOT a measured relevance score. */
export function keywordHits(o: Opportunity, query: string): number {
  const q = tokens(query);
  if (q.length === 0) return 0;
  const hay = `${o.title} ${o.organization ?? ""} ${o.description} ${o.tags.join(" ")} ${o.location ?? ""} ${o.fieldsOfStudy.join(" ")}`.toLowerCase();
  return q.filter((t) => hay.includes(t)).length;
}

export function matchesFilters(o: Opportunity, f: FilterState, now = new Date()): boolean {
  if (f.query.trim() && tokens(f.query).length && keywordHits(o, f.query) === 0) return false;
  if (f.category !== "all" && o.category !== f.category) return false;
  if (f.location !== "all" && !(o.location ?? "").toLowerCase().includes(f.location.toLowerCase())) return false;
  if (f.field !== "all" && !o.fieldsOfStudy.some((x) => x === f.field || x === "Any")) return false;
  if (f.level !== "all" && !o.educationLevels.some((l) => l === f.level || l === "any")) return false;
  if (f.workMode !== "all" && o.workMode !== f.workMode) return false;
  if (f.organization !== "all" && o.organization !== f.organization) return false;
  if (f.status !== "all" && o.applicationState !== f.status) return false;
  if (f.deadline === "none") {
    if (o.deadline) return false;
  } else if (f.deadline !== "any") {
    const n = daysUntil(o.deadline, now);
    if (n === null || n < 0 || n > Number(f.deadline)) return false;
  }
  return true;
}

export function sortOpportunities(list: Opportunity[], f: FilterState): Opportunity[] {
  const indexed = list.map((o, i) => ({ o, i }));
  switch (f.sort) {
    case "deadline":
      // Unknown deadlines sort last; they are never treated as "soonest".
      indexed.sort((a, b) => {
        const da = a.o.deadline ? Date.parse(a.o.deadline) : Infinity;
        const db = b.o.deadline ? Date.parse(b.o.deadline) : Infinity;
        return da - db || a.i - b.i;
      });
      break;
    case "completeness":
      indexed.sort((a, b) => {
        const ca = a.o.verification ? coverageScore(a.o.verification.counts)?.percent ?? -1 : -1;
        const cb = b.o.verification ? coverageScore(b.o.verification.counts)?.percent ?? -1 : -1;
        return cb - ca || a.i - b.i;
      });
      break;
    default:
      if (f.query.trim()) indexed.sort((a, b) => keywordHits(b.o, f.query) - keywordHits(a.o, f.query) || a.i - b.i);
  }
  return indexed.map((x) => x.o);
}

export function optionsFrom(list: Opportunity[]) {
  const uniq = (xs: (string | null | undefined)[]) => [...new Set(xs.filter((x): x is string => !!x && x !== "Any"))].sort();
  return {
    locations: uniq(list.map((o) => o.location)),
    fields: uniq(list.flatMap((o) => o.fieldsOfStudy)),
    organizations: uniq(list.map((o) => o.organization)),
  };
}
