"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Opportunity } from "@/types";
import { api } from "@/lib/api-client";
import { describeError } from "@/lib/api-errors";
import { DEMO_OPPORTUNITIES, DEMO_SAVED_IDS } from "@/lib/dev-fixtures/demo-data";
import { mapOpportunities } from "@/lib/mappers";
import { useDemo } from "@/providers/DemoProvider";
import { useToast } from "@/providers/ToastProvider";

interface SavedCtx {
  items: Opportunity[];
  savedAt: Record<string, string>;
  loading: boolean;
  error: unknown;
  isSaved: (id: string) => boolean;
  toggle: (opp: Opportunity) => Promise<void>;
  remove: (id: string) => Promise<void>;
  reload: () => void;
}

const Ctx = createContext<SavedCtx | null>(null);
const KEY = "verifai.saved.sample";
const DEFAULT_SAVED_AT = "2026-10-18T10:00:00Z";

export function SavedProvider({ children }: { children: React.ReactNode }) {
  const { demo, ready } = useDemo();
  const toast = useToast();
  const [items, setItems] = useState<Opportunity[]>([]);
  const [savedAt, setSavedAt] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!ready) return;
    setError(null);
    if (demo) {
      // Sample mode keeps saved ids in this browser only.
      let stored: Record<string, string> | null = null;
      try {
        const raw = window.localStorage.getItem(KEY);
        if (raw) stored = JSON.parse(raw) as Record<string, string>;
      } catch {
        /* ignore */
      }
      const map = stored ?? Object.fromEntries(DEMO_SAVED_IDS.map((id) => [id, DEFAULT_SAVED_AT]));
      setSavedAt(map);
      setItems(DEMO_OPPORTUNITIES.filter((o) => o.id in map));
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    api
      .get<{ items?: unknown; saved_at?: Record<string, string> }>("/api/v1/saved", undefined, ctrl.signal)
      .then((raw) => {
        const list = mapOpportunities(raw.items);
        setItems(list);
        setSavedAt(raw.saved_at ?? {});
        setLoading(false);
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setItems([]);
        setError(e);
        setLoading(false);
      });
    return () => ctrl.abort();
  }, [demo, ready, tick]);

  const persistSample = useCallback((map: Record<string, string>) => {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(map));
    } catch {
      /* ignore */
    }
  }, []);

  const ids = useMemo(() => new Set(items.map((o) => o.id)), [items]);

  const add = useCallback(
    async (opp: Opportunity) => {
      if (demo) {
        const map = { ...savedAt, [opp.id]: new Date().toISOString() };
        setSavedAt(map);
        setItems((xs) => [...xs, opp]);
        persistSample(map);
      } else {
        await api.put(`/api/v1/saved/${encodeURIComponent(opp.id)}`);
        setSavedAt((m) => ({ ...m, [opp.id]: new Date().toISOString() }));
        setItems((xs) => [...xs, opp]);
      }
    },
    [demo, savedAt, persistSample],
  );

  const remove = useCallback(
    async (id: string) => {
      try {
        if (!demo) await api.delete(`/api/v1/saved/${encodeURIComponent(id)}`);
        const { [id]: _removed, ...rest } = savedAt;
        void _removed;
        setSavedAt(rest);
        setItems((xs) => xs.filter((o) => o.id !== id));
        if (demo) persistSample(rest);
        toast({ tone: "info", title: "Removed from saved" });
      } catch (e) {
        const d = describeError(e);
        toast({ tone: "error", title: "Could not remove", body: d.message });
      }
    },
    [demo, savedAt, persistSample, toast],
  );

  const toggle = useCallback(
    async (opp: Opportunity) => {
      if (ids.has(opp.id)) return remove(opp.id);
      try {
        await add(opp);
        toast({ tone: "success", title: "Saved", body: demo ? "Stored in this browser (sample mode)." : undefined });
      } catch (e) {
        const d = describeError(e);
        toast({ tone: "error", title: "Could not save", body: d.message });
      }
    },
    [ids, add, remove, toast, demo],
  );

  const value = useMemo<SavedCtx>(
    () => ({ items, savedAt, loading, error, isSaved: (id) => ids.has(id), toggle, remove, reload: () => setTick((t) => t + 1) }),
    [items, savedAt, loading, error, ids, toggle, remove],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSaved(): SavedCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSaved must be used within SavedProvider");
  return v;
}
