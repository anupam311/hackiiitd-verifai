"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { DEMO_DEFAULT } from "@/lib/config";

interface DemoCtx {
  /** True when development fixtures are used instead of the backend. */
  demo: boolean;
  /** False until the stored preference has been read (avoids double fetching). */
  ready: boolean;
  setDemo: (v: boolean) => void;
}

const Ctx = createContext<DemoCtx | null>(null);
const KEY = "verifai.sample-data";

export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [demo, setDemoState] = useState(DEMO_DEFAULT);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(KEY);
      if (stored === "on") setDemoState(true);
      else if (stored === "off") setDemoState(false);
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  const setDemo = useCallback((v: boolean) => {
    setDemoState(v);
    try {
      window.localStorage.setItem(KEY, v ? "on" : "off");
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(() => ({ demo, ready, setDemo }), [demo, ready, setDemo]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDemo(): DemoCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useDemo must be used within DemoProvider");
  return v;
}
