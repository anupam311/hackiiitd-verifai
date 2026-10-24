import type { DiscoverySearchRequest, DiscoverySearchResponse, Opportunity } from "@/types";
import { api } from "@/lib/api-client";
import { ApiError } from "@/lib/api-errors";
import { DEMO_OPPORTUNITIES } from "@/lib/dev-fixtures/demo-data";
import { mapOpportunities, mapOpportunity } from "@/lib/mappers";
import { keywordHits } from "./filters";

const SAMPLE_WARNING = "Sample data is switched on. These results are development fixtures, not live search results.";

export async function searchOpportunities(demo: boolean, req: DiscoverySearchRequest, signal?: AbortSignal): Promise<DiscoverySearchResponse> {
  if (demo) {
    const q = req.query.trim();
    const list = q ? DEMO_OPPORTUNITIES.filter((o) => keywordHits(o, q) > 0) : DEMO_OPPORTUNITIES;
    return { run_id: null, state: "completed", opportunities: list, warnings: [SAMPLE_WARNING] };
  }
  const raw = await api.post<{ run_id: string | null; state: DiscoverySearchResponse["state"]; opportunities: unknown; warnings?: string[] }>(
    "/api/v1/discovery/search",
    req,
    signal,
  );
  return {
    run_id: raw.run_id ?? null,
    state: raw.state ?? "partial",
    opportunities: mapOpportunities(raw.opportunities),
    warnings: raw.warnings ?? [],
  };
}

/** Browse previously stored opportunities (no search query). */
export async function listOpportunities(demo: boolean, signal?: AbortSignal): Promise<DiscoverySearchResponse> {
  if (demo) return { run_id: null, state: "completed", opportunities: DEMO_OPPORTUNITIES, warnings: [SAMPLE_WARNING] };
  const raw = await api.get<{ items?: unknown; note?: string }>("/api/v1/opportunities", undefined, signal);
  return { run_id: null, state: "completed", opportunities: mapOpportunities(raw.items), warnings: raw.note ? [raw.note] : [] };
}

export async function getOpportunity(demo: boolean, id: string, signal?: AbortSignal): Promise<Opportunity> {
  if (demo) {
    const found = DEMO_OPPORTUNITIES.find((o) => o.id === id);
    if (!found) throw new ApiError({ kind: "not_implemented", message: "This sample opportunity does not exist.", status: 404 });
    return found;
  }
  const raw = await api.get<unknown>(`/api/v1/opportunities/${encodeURIComponent(id)}`, undefined, signal);
  const mapped = mapOpportunity(raw);
  if (!mapped) throw new ApiError({ kind: "unknown", message: "The API returned an opportunity in an unexpected shape." });
  return mapped;
}
