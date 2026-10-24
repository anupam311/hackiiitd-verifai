import type { Snapshot } from "@/types";
import { api } from "@/lib/api-client";
import { DEMO_HISTORY } from "@/lib/dev-fixtures/demo-data";
import { mapSnapshots } from "@/lib/mappers";

export async function getHistory(demo: boolean, opportunityId: string, signal?: AbortSignal): Promise<Snapshot[]> {
  if (demo) return DEMO_HISTORY[opportunityId] ?? [];
  const raw = await api.get<unknown>(`/api/v1/opportunities/${encodeURIComponent(opportunityId)}/history`, undefined, signal);
  return mapSnapshots(raw, opportunityId);
}
