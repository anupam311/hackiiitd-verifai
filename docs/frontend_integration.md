# Frontend ↔ Backend Integration

Single client: `frontend/src/lib/api-client.ts` (base URL from `NEXT_PUBLIC_API_BASE_URL`, `credentials: "include"` for the HttpOnly session cookie). Errors follow `docs/api.md` and map to `ApiError` kinds (`network`, `not_implemented` for 404/405/501, `unauthenticated`, `validation`, `rate_limited`, `server`).

| UI feature | Endpoint | Status vs. current backend |
|---|---|---|
| Discover (query) | `POST /api/v1/discovery/search` | Exists; returns `state: "partial"` + warning while provider is unconfigured — shown as a partial-results notice |
| Discover (browse) | `GET /api/v1/opportunities` | Exists; empty list → empty state |
| Opportunity detail | `GET /api/v1/opportunities/{id}` | Placeholder → “not found / not available” |
| Report | `GET …/{id}/report` | Placeholder → “No verification report yet” |
| Sources | `GET …/{id}/sources` | Falls back to deriving comparison from the report |
| Recheck | `POST …/{id}/recheck` → `{run_id}` | Placeholder → toast explaining it is unavailable |
| Run progress | `GET /api/v1/runs/{id}` (polled); SSE URL helper `runEventsUrl` ready | Placeholder |
| History | `GET …/{id}/history` | Placeholder |
| Saved | `GET /api/v1/saved`, `PUT|DELETE /api/v1/saved/{id}` | Placeholder → error state, never fake success |
| Profile | `GET|PATCH /api/v1/profile` | Optional; profile is kept locally and synced when available |
| Auth | `/auth/google/login`, `/auth/github/login`, `GET /auth/me`, `POST /auth/logout` | Links/calls ready; needs provider credentials |
| Notifications | `GET /api/v1/notifications` | **Not in api.md** — UI shows “not available yet” |

Payload shapes are normalised in `src/lib/mappers.ts` (accepts the backend's snake_case models `ClaimResult`, `SourceObservation`, `OpportunitySummary`). Fields the backend doesn't send yet (e.g. `original_wording`, `unresolved_questions`, `limitations`, per-source `outcome`) are optional in the UI; when the report endpoint is implemented, add them to the Pydantic models with those names.
