"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export type ApiHealth = "checking" | "up" | "down";

/** One-shot `GET /health` probe so users can tell whether live mode can work. */
export function useApiHealth(enabled: boolean): ApiHealth {
  const [state, setState] = useState<ApiHealth>("checking");
  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    setState("checking");
    api
      .get<{ status?: string }>("/health", undefined, ctrl.signal)
      .then((r) => setState(r?.status === "ok" ? "up" : "down"))
      .catch(() => {
        if (!ctrl.signal.aborted) setState("down");
      });
    return () => ctrl.abort();
  }, [enabled]);
  return state;
}
