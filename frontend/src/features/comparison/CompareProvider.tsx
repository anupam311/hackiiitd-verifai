"use client";

import { createContext, useCallback, useContext, useMemo } from "react";
import type { Opportunity } from "@/types";
import { useStoredState } from "@/hooks/useStoredState";
import { useToast } from "@/providers/ToastProvider";

export const MAX_COMPARE = 3;

interface CompareCtx {
  selected: Opportunity[];
  isSelected: (id: string) => boolean;
  toggle: (opp: Opportunity) => void;
  clear: () => void;
}
const Ctx = createContext<CompareCtx | null>(null);

/** Selection holds snapshots of opportunity records so the workspace works after navigation. */
export function CompareProvider({ children }: { children: React.ReactNode }) {
  const [selected, setSelected] = useStoredState<Opportunity[]>("verifai.compare", []);
  const toast = useToast();

  const toggle = useCallback(
    (opp: Opportunity) => {
      if (selected.some((o) => o.id === opp.id)) {
        setSelected((xs) => xs.filter((o) => o.id !== opp.id));
      } else if (selected.length >= MAX_COMPARE) {
        toast({ tone: "info", title: `You can compare up to ${MAX_COMPARE} opportunities`, body: "Remove one to add another." });
      } else {
        setSelected((xs) => [...xs, opp]);
      }
    },
    [selected, setSelected, toast],
  );

  const value = useMemo<CompareCtx>(
    () => ({ selected, isSelected: (id) => selected.some((o) => o.id === id), toggle, clear: () => setSelected([]) }),
    [selected, toggle, setSelected],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCompare(): CompareCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCompare must be used within CompareProvider");
  return v;
}
