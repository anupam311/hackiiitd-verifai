"use client";

import { useEffect, useState } from "react";
import type { Run } from "@/types";
import { getRun } from "./api";

const TERMINAL = new Set(["completed", "partial", "failed", "cancelled"]);

/**
 * Follows a real backend run by polling `GET /api/v1/runs/{id}` (docs/api.md).
 * No timers fabricate progress: every step shown comes from a returned event.
 * An SSE endpoint exists at `/runs/{id}/events` (see `runEventsUrl`) and can replace polling later.
 */
export function useRun(runId: string | null, demo: boolean, intervalMs = 2000): { run: Run | null; error: unknown } {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const ctrl = new AbortController();

    const tick = async () => {
      try {
        const next = await getRun(demo, runId, ctrl.signal);
        if (stopped) return;
        setRun(next);
        setError(null);
        if (TERMINAL.has(next.state) || demo) return;
      } catch (e) {
        if (stopped || (e instanceof DOMException && e.name === "AbortError")) return;
        setError(e);
        return; // stop on error; the UI offers a retry by remounting
      }
      timer = setTimeout(tick, intervalMs);
    };
    void tick();
    return () => {
      stopped = true;
      ctrl.abort();
      if (timer) clearTimeout(timer);
    };
  }, [runId, demo, intervalMs]);

  return { run, error };
}
