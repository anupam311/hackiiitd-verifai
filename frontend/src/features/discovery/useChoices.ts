"use client";

import { useMemo } from "react";
import type { Opportunity } from "@/types";
import { useAsync } from "@/hooks/useAsync";
import { useSaved } from "@/features/saved/SavedProvider";
import { useDemo } from "@/providers/DemoProvider";
import { listOpportunities } from "./api";

/** Opportunities the user can pick from in Recheck / History / Compare / Checklist / Passport: saved first, then stored ones. */
export function useOpportunityChoices(): { choices: Opportunity[]; loading: boolean; error: unknown; reload: () => void } {
  const { demo, ready } = useDemo();
  const saved = useSaved();
  const all = useAsync((s) => listOpportunities(demo, s), [demo], ready);
  const choices = useMemo(() => {
    const map = new Map<string, Opportunity>();
    for (const o of saved.items) map.set(o.id, o);
    for (const o of all.data?.opportunities ?? []) if (!map.has(o.id)) map.set(o.id, o);
    return [...map.values()];
  }, [saved.items, all.data]);
  return { choices, loading: all.loading || saved.loading, error: all.error, reload: all.reload };
}
