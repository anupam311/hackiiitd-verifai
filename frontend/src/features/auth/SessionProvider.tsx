"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { SessionUser } from "@/types";
import { api } from "@/lib/api-client";
import { ApiError } from "@/lib/api-errors";
import { useDemo } from "@/providers/DemoProvider";

export type SessionStatus = "loading" | "authenticated" | "anonymous" | "unavailable";

interface SessionCtx {
  status: SessionStatus;
  user: SessionUser | null;
  /** True when the user is the sample applicant (sample-data mode), not a real account. */
  isSample: boolean;
  logout: () => Promise<void>;
  refresh: () => void;
}

const Ctx = createContext<SessionCtx | null>(null);
const SAMPLE_USER: SessionUser = { id: "sample-user", email: null, displayName: "Sample Applicant" };

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { demo, ready } = useDemo();
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [user, setUser] = useState<SessionUser | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!ready) return;
    if (demo) {
      setUser(SAMPLE_USER);
      setStatus("authenticated");
      return;
    }
    const ctrl = new AbortController();
    setStatus("loading");
    api
      .get<Record<string, unknown>>("/auth/me", undefined, ctrl.signal)
      .then((raw) => {
        const id = typeof raw.id === "string" ? raw.id : null;
        if (!id) {
          setUser(null);
          setStatus("anonymous");
          return;
        }
        setUser({
          id,
          email: typeof raw.email === "string" ? raw.email : null,
          displayName: (typeof raw.display_name === "string" && raw.display_name) || (typeof raw.name === "string" && raw.name) || "Signed-in user",
          avatarUrl: typeof raw.avatar_url === "string" ? raw.avatar_url : null,
        });
        setStatus("authenticated");
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return;
        setUser(null);
        // 401 = reachable but signed out. Anything else = we cannot tell.
        setStatus(e instanceof ApiError && (e.kind === "unauthenticated" || e.kind === "not_implemented") ? "anonymous" : "unavailable");
      });
    return () => ctrl.abort();
  }, [demo, ready, tick]);

  const logout = useCallback(async () => {
    if (!demo) await api.post("/auth/logout");
    setUser(null);
    setStatus("anonymous");
  }, [demo]);

  const value = useMemo<SessionCtx>(() => ({ status, user, isSample: demo, logout, refresh: () => setTick((t) => t + 1) }), [status, user, demo, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession must be used within SessionProvider");
  return v;
}
