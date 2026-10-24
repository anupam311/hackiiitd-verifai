import type { Run, SourceComparison, VerificationReport } from "@/types";
import { api } from "@/lib/api-client";
import { ApiError } from "@/lib/api-errors";
import { DEMO_REPORTS, DEMO_RUN } from "@/lib/dev-fixtures/demo-data";
import { mapReport, mapRun } from "@/lib/mappers";
import { buildComparison } from "./compare";

export async function getReport(demo: boolean, opportunityId: string, signal?: AbortSignal): Promise<VerificationReport> {
  if (demo) {
    const r = DEMO_REPORTS[opportunityId];
    if (!r) throw new ApiError({ kind: "not_implemented", message: "No sample report exists for this opportunity.", status: 404 });
    return r;
  }
  const raw = await api.get<unknown>(`/api/v1/opportunities/${encodeURIComponent(opportunityId)}/report`, undefined, signal);
  return mapReport(raw, opportunityId);
}

/** Prefers the backend `/sources` endpoint; falls back to deriving from the report. */
export async function getSources(demo: boolean, opportunityId: string, signal?: AbortSignal): Promise<SourceComparison> {
  if (demo) return buildComparison(await getReport(true, opportunityId));
  try {
    const raw = await api.get<unknown>(`/api/v1/opportunities/${encodeURIComponent(opportunityId)}/sources`, undefined, signal);
    const rec = raw as Partial<SourceComparison> | null;
    if (rec && Array.isArray(rec.rows) && Array.isArray(rec.sources)) return { opportunityId, sources: rec.sources, rows: rec.rows };
    return buildComparison(mapReport(raw, opportunityId));
  } catch (e) {
    if (e instanceof ApiError && e.kind === "not_implemented") return buildComparison(await getReport(false, opportunityId, signal));
    throw e;
  }
}

export interface RecheckStart {
  runId: string;
}

export async function startRecheck(opportunityId: string): Promise<RecheckStart> {
  const raw = await api.post<{ run_id?: string }>(`/api/v1/opportunities/${encodeURIComponent(opportunityId)}/recheck`);
  if (!raw?.run_id) throw new ApiError({ kind: "unknown", message: "The API did not return a run id for this recheck." });
  return { runId: raw.run_id };
}

export async function getRun(demo: boolean, runId: string, signal?: AbortSignal): Promise<Run> {
  if (demo) return DEMO_RUN;
  return mapRun(await api.get<unknown>(`/api/v1/runs/${encodeURIComponent(runId)}`, undefined, signal));
}
