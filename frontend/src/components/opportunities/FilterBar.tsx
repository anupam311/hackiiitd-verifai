"use client";

import { RotateCcw, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import type { Opportunity } from "@/types";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { activeFilterCount, DEFAULT_FILTERS, optionsFrom, type FilterState } from "@/features/discovery/filters";
import { CATEGORY_LABEL, EDUCATION_LABEL } from "@/lib/formatters";

const opts = (all: string, items: string[]) => [{ value: "all", label: all }, ...items.map((i) => ({ value: i, label: i }))];

export function FilterBar({ filters, onChange, results }: { filters: FilterState; onChange: (f: FilterState) => void; results: Opportunity[] }) {
  const [more, setMore] = useState(false);
  const o = optionsFrom(results);
  const set = <K extends keyof FilterState>(k: K, v: FilterState[K]) => onChange({ ...filters, [k]: v });
  const count = activeFilterCount(filters);

  return (
    <div className="filters" role="group" aria-label="Filters">
      <div className="filter-row">
        <Select label="Category" value={filters.category} onChange={(v) => set("category", v as FilterState["category"])} options={[{ value: "all", label: "All categories" }, ...Object.entries(CATEGORY_LABEL).map(([value, label]) => ({ value, label }))]} />
        <Select label="Location" value={filters.location} onChange={(v) => set("location", v)} options={opts("Location", o.locations)} />
        <Select label="Field of study" value={filters.field} onChange={(v) => set("field", v)} options={opts("Field of study", o.fields)} />
        <Select
          label="Deadline"
          value={filters.deadline}
          onChange={(v) => set("deadline", v as FilterState["deadline"])}
          options={[
            { value: "any", label: "Any deadline" },
            { value: "30", label: "Within 30 days" },
            { value: "60", label: "Within 60 days" },
            { value: "90", label: "Within 90 days" },
            { value: "none", label: "No known deadline" },
          ]}
        />
        <Select label="Education level" value={filters.level} onChange={(v) => set("level", v)} options={[{ value: "all", label: "Level" }, ...(["high_school", "undergraduate", "postgraduate", "doctoral"] as const).map((v) => ({ value: v, label: EDUCATION_LABEL[v] }))]} />
        <Button variant="secondary" aria-expanded={more} aria-controls="more-filters" icon={<SlidersHorizontal size={15} aria-hidden />} onClick={() => setMore((m) => !m)}>
          More filters
        </Button>
        {count > 0 && (
          <Button variant="ghost" icon={<RotateCcw size={14} aria-hidden />} onClick={() => onChange({ ...DEFAULT_FILTERS, query: filters.query, sort: filters.sort })}>
            Reset ({count})
          </Button>
        )}
      </div>
      {more && (
        <div className="filter-row filter-row-more" id="more-filters">
          <Select label="Work mode" value={filters.workMode} onChange={(v) => set("workMode", v as FilterState["workMode"])} options={[{ value: "all", label: "Remote / on-site" }, { value: "remote", label: "Remote" }, { value: "on_site", label: "On-site" }, { value: "hybrid", label: "Hybrid" }]} />
          <Select label="Organisation" value={filters.organization} onChange={(v) => set("organization", v)} options={opts("Organisation", o.organizations)} />
          <Select label="Application status (as listed)" value={filters.status} onChange={(v) => set("status", v as FilterState["status"])} options={[{ value: "all", label: "Any status" }, { value: "open", label: "Listed as open" }, { value: "rolling", label: "Rolling" }, { value: "unknown", label: "Status unknown" }]} />
        </div>
      )}
    </div>
  );
}
