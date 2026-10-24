import type { ApiErrorEnvelope } from "@/types";

export type ApiErrorKind =
  | "network" // backend unreachable / CORS / offline
  | "not_implemented" // 404/405/501 on an endpoint that is still a placeholder
  | "unauthenticated"
  | "forbidden"
  | "validation"
  | "rate_limited"
  | "server"
  | "unknown";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string | null;
  readonly requestId: string | null;

  constructor(opts: { kind: ApiErrorKind; message: string; status?: number | null; code?: string | null; requestId?: string | null }) {
    super(opts.message);
    this.name = "ApiError";
    this.kind = opts.kind;
    this.status = opts.status ?? null;
    this.code = opts.code ?? null;
    this.requestId = opts.requestId ?? null;
  }
}

function kindFromStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthenticated";
  if (status === 403) return "forbidden";
  if (status === 404 || status === 405 || status === 501) return "not_implemented";
  if (status === 400 || status === 422) return "validation";
  if (status === 429) return "rate_limited";
  if (status >= 500) return "server";
  return "unknown";
}

function isEnvelope(v: unknown): v is ApiErrorEnvelope {
  return typeof v === "object" && v !== null && "error" in v && typeof (v as ApiErrorEnvelope).error?.message === "string";
}

/** Convert a non-2xx response into an ApiError, honouring docs/api.md's error shape. */
export async function errorFromResponse(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* body is not JSON */
  }
  if (isEnvelope(body)) {
    return new ApiError({
      kind: kindFromStatus(res.status),
      message: body.error.message,
      status: res.status,
      code: body.error.code,
      requestId: body.error.request_id ?? null,
    });
  }
  return new ApiError({ kind: kindFromStatus(res.status), message: `Request failed with status ${res.status}.`, status: res.status });
}

export function networkError(): ApiError {
  return new ApiError({
    kind: "network",
    message: "Could not reach the VERIFAI API. Check that the backend is running and NEXT_PUBLIC_API_BASE_URL is correct.",
  });
}

/** Short, user-facing explanation for any thrown value. */
export function describeError(err: unknown): { title: string; message: string; retryable: boolean } {
  if (err instanceof ApiError) {
    switch (err.kind) {
      case "network":
        return { title: "Backend unreachable", message: err.message, retryable: true };
      case "not_implemented":
        return {
          title: "Not available yet",
          message: "This backend endpoint is not implemented in the current API build. Nothing was changed.",
          retryable: false,
        };
      case "unauthenticated":
        return { title: "Sign-in required", message: "Sign in to use this feature.", retryable: false };
      case "rate_limited":
        return { title: "Too many requests", message: "The API is rate limiting requests. Try again shortly.", retryable: true };
      case "server":
        return { title: "Server error", message: err.message + (err.requestId ? ` (request ${err.requestId})` : ""), retryable: true };
      default:
        return { title: "Request failed", message: err.message, retryable: true };
    }
  }
  return { title: "Something went wrong", message: err instanceof Error ? err.message : "Unexpected error.", retryable: true };
}
