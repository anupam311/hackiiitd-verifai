"use client";

import { Select } from "@/components/ui/Field";
import type { Opportunity } from "@/types";

export function OpportunityPicker({ choices, value, onChange, label = "Opportunity" }: { choices: Opportunity[]; value: string; onChange: (id: string) => void; label?: string }) {
  return (
    <Select
      label={label}
      hideLabel={false}
      value={value}
      onChange={onChange}
      options={[{ value: "", label: choices.length ? "Select an opportunity…" : "No opportunities available" }, ...choices.map((o) => ({ value: o.id, label: `${o.title} — ${o.organization ?? "Unknown organisation"}` }))]}
    />
  );
}
