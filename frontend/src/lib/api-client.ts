import { API_BASE_URL } from "./config";
import { ApiError, errorFromResponse, networkError } from "./api-errors";

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null | string[]>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(path.startsWith("http") ? path : `${API_BASE_URL}${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null || v === "") continue;
      if (Array.isArray(v)) v.forEach((item) => url.searchParams.append(k, item));
      else url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

/**
 * Single entry point for backend communication. Session cookies are HttpOnly
 * and set by the backend (docs/api.md), so requests use `credentials: include`.
 */
export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? "GET",
      headers: opts.body !== undefined ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      credentials: "include",
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw networkError();
  }
  if (!res.ok) throw await errorFromResponse(res);
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError({ kind: "unknown", message: "The API returned a response that was not valid JSON.", status: res.status });
  }
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal) => apiRequest<T>(path, { query, signal }),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) => apiRequest<T>(path, { method: "POST", body, signal }),
  put: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: "DELETE" }),
};

export const authUrls = {
  google: `${API_BASE_URL}/auth/google/login`,
  github: `${API_BASE_URL}/auth/github/login`,
};

export function runEventsUrl(runId: string): string {
  return `${API_BASE_URL}/api/v1/runs/${encodeURIComponent(runId)}/events`;
}
