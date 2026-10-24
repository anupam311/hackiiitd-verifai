"use client";

import { useStoredState } from "@/hooks/useStoredState";

/** Completed checklist item ids per opportunity, stored in this browser only. */
export function useChecklistProgress(opportunityId: string) {
  const [done, setDone, hydrated] = useStoredState<string[]>(`verifai.checklist.${opportunityId}`, []);
  const set = new Set(done);
  return {
    hydrated,
    isDone: (id: string) => set.has(id),
    toggle: (id: string) => setDone((xs) => (xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id])),
    reset: () => setDone([]),
    count: done.length,
  };
}
