# VERIFAI API Contract (MVP)

Base URL in development: `http://localhost:8000`. JSON is used for request and response bodies. All user-owned resources require a valid session once authentication is enabled.

## Health
### `GET /health`
Returns `{ "status": "ok", "service": "verifai-api" }`.

## Discovery
### `POST /api/v1/discovery/search`
Request limits (schema defined; the endpoint arrives in a later commit): `query` is required, 1-500 characters; `limit` is 1-50 (default 20); at most 10 `categories` and 10 `fields_of_study`. Category values: `internship`, `scholarship`, `fellowship`, `job`, `research`, `competition`, `other`. Violations return `400 VALIDATION_ERROR`. `state` is one of `queued`, `running`, `completed`, `partial`, `failed`.

Errors: `400 VALIDATION_ERROR`, `429 RATE_LIMITED` (too many runs active), `503 SERVICE_UNAVAILABLE` (no discovery provider or LLM credentials configured).

Request:
```json
{
  "query": "software engineering internships",
  "location": "Bengaluru, India",
  "categories": ["internship"],
  "fields_of_study": ["computer science"],
  "deadline_before": "2026-12-31",
  "limit": 20
}
```
Response: `{ "run_id": "…", "state": "queued|running|completed|partial|failed", "opportunities": [], "warnings": [] }`.

### Runs (implemented)
- `GET /api/v1/runs/{run_id}?after=N` returns `{run_id, kind, state, started_at, completed_at, elapsed_s, opportunities, warnings, error_code, last_seq, events}`. `opportunities` fills in as each report becomes ready (partial results). `events` contains only events with `seq` greater than `after`.
- `GET /api/v1/runs/{run_id}/events` is a Server-Sent Events stream of the same events. Each message has `id: <seq>`, `event: <type>` and a JSON `data` payload. Reconnect with the `Last-Event-ID` header (or `?after=`) to resume. The stream ends after the final event. Comment lines (`: keep-alive`) are sent periodically.
- `POST /api/v1/runs/{run_id}/cancel` returns `202` and is idempotent. Pending work stops; opportunities already saved are kept; the final state is `cancelled`.
- Unknown run ids return `404 NOT_FOUND`.

### Listing, history and recheck (implemented)
- `GET /api/v1/opportunities?q=&category=&limit=&offset=` returns `{items, limit, offset}`, newest first. `q` matches title or organization (wildcard characters are literal). `limit` is 1-50 (default 20). Filters for location, deadline and level are not implemented yet.
- `GET /api/v1/opportunities/{id}/history?limit=` returns `{opportunity_id, runs}`, newest first. Each run has `run_id`, `generated_at`, `status`, `summary`, and `changes_since_previous` (null for the oldest snapshot). Changes list each claim that `changed`, `appeared`, `disappeared` or `became_stale`, with old and new status and value, plus `unchanged` count and `status_before`/`status_after`.
- `POST /api/v1/opportunities/{id}/recheck` (login required) starts a run and returns `202 {run_id, state}`. Errors: `401`, `404` (unknown opportunity, or no earlier report so there are no sources to recheck), `409` (a recheck for this opportunity is already running), `429`, `503` (provider or LLM not configured). Follow it with the Runs endpoints; its events include `recheck.started` and `recheck.diff`. A cancelled or failed recheck leaves history unchanged.

### Saved opportunities (implemented, login required)
- `GET /api/v1/saved` returns each saved opportunity with `saved_at`, `latest_status`, `latest_summary` and `latest_report_at`.
- `PUT /api/v1/saved/{id}` is idempotent (the original `saved_at` is kept). `404` if the opportunity does not exist.
- `DELETE /api/v1/saved/{id}` returns `204` whether or not it was saved, and `404` if the opportunity does not exist.

Saved lists are per user. Without a valid session these routes return `401 UNAUTHENTICATED`.

Event types: `run.started`, `discovery.started`, `discovery.retry` (`attempt`, `code`, `delay_s`), `discovery.completed` (`records`, `complete`), `normalize.completed` (`observations`, `rejected`, `duplicates`), `extract.started`, `extract.completed` (`facts`, `dropped`), `extract.failed` (`code`), `source.unavailable` (`domain`, `outcome`), `source.no_content`, `opportunity.ready` (`opportunity_id`), and one final event: `run.completed`, `run.partial`, `run.failed` (with `error_code`) or `run.cancelled`.

Events are produced by the pipeline as it works. They never include the search text or page content.

State rules: `completed` means every step succeeded; `partial` means some sources failed extraction, some records were invalid, or the provider returned an incomplete result; `failed` means a provider or credential error stopped the run (`error_code` says which). A source that cannot be retrieved produces a warning, not a failure, and is never treated as evidence the opportunity is closed.

## Opportunities
- `GET /api/v1/opportunities` — paginated/filterable opportunities.
- `GET /api/v1/opportunities/{opportunity_id}` — normalized opportunity details.
- `GET /api/v1/opportunities/{opportunity_id}/report` — latest verification report and evidence.
- `POST /api/v1/opportunities/{opportunity_id}/recheck` — start a new verification run.
- `GET /api/v1/opportunities/{opportunity_id}/history` — prior snapshots and changes.
- `GET /api/v1/opportunities/{opportunity_id}/sources` — source observations and source comparison.

### Implemented response shapes
`GET /api/v1/opportunities/{id}` returns the opportunity. `is_demo` is true for seeded demo data; `status` is `unknown` unless a confirmed `application_status` claim says otherwise.

`GET /api/v1/opportunities/{id}/report` returns `{run_id, opportunity_id, generated_at, status, summary, claims, sources}`.
- `summary`: `{total, counts, score_percent, discrepancies, formula}`. `score_percent` is a coverage score, not a probability; `formula` explains it.
- Each claim has `claim_type`, `status`, `normalized_value`, `explanation`, `next_step`, `checked_at`, `stale`, `needs_review` and `evidence[]`.
- Each evidence entry has `url`, `domain`, `source_type`, `retrieved_at`, `extracted_value`, `normalized_value`, `excerpt`, `evidence_locator`, `confidence` (extraction confidence), `is_authoritative`, `is_fresh` and `role` (`supports`, `discrepant`, `conflicting`, `ambiguous`).

`GET /api/v1/opportunities/{id}/sources` returns `{sources, rows, conflicts, warnings}`.
- `sources` are ordered official/employer/institution first and include sources that failed to load, with their `retrieval_outcome`.
- Each row is one claim: `agreement` is `agree`, `partial`, `conflict` or `missing`, with a cell per source (`agrees`, `differs`, `ambiguous`, `missing`, `unavailable`).
- `conflicts` lists the values from every source involved. `warnings` covers stale evidence and failed retrievals.

Both report endpoints return `404 NOT_FOUND` when the opportunity or its report does not exist.

## Saved opportunities
- `GET /api/v1/saved` — current user's saved opportunities.
- `PUT /api/v1/saved/{opportunity_id}` — save an opportunity; idempotent.
- `DELETE /api/v1/saved/{opportunity_id}` — remove a saved opportunity.

## Profile
- `GET /api/v1/profile` — authenticated user's profile.
- `PATCH /api/v1/profile` — update education, location, experience, and interests.

## Runs
- `GET /api/v1/runs/{run_id}` — progress and partial output.
- `GET /api/v1/runs/{run_id}/events` — SSE progress stream in the production implementation.

## Authentication
- `GET /auth/google/login`
- `GET /auth/google/callback`
- `GET /auth/github/login`
- `GET /auth/github/callback`
- `POST /auth/logout`
- `GET /auth/me`

OAuth callbacks must validate state and, for OIDC, nonce; exchange tokens on the server; verify identity; and set an `HttpOnly`, `Secure` (in production), `SameSite=Lax` session cookie. Do not expose provider secrets or access tokens to the browser. GitHub email may be private or unverified; handle that case explicitly. Account linking requires a verified matching email or a deliberate authenticated linking flow.

## Standard error shape
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be processed.",
    "request_id": "req_..."
  }
}
```
Use appropriate HTTP status codes: 400 invalid input, 401 unauthenticated, 403 unauthorized, 404 missing resource, 409 state conflict, 429 rate limit, and 500 unexpected failure. Never return secrets, raw provider tokens, or full unredacted source payloads by default.

### Error codes and headers (implemented)
| Status | `code` |
|---|---|
| 400 | `VALIDATION_ERROR` (invalid body or params), `BAD_REQUEST` |
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN` |
| 404 | `NOT_FOUND` |
| 409 | `CONFLICT` |
| 429 | `RATE_LIMITED` |
| 500 | `INTERNAL_ERROR` |

Every response, success or error, includes an `X-Request-ID` header; for errors it equals `error.request_id`. Validation errors do not echo submitted values. `/docs` and `/openapi.json` are disabled when `VERIFAI_ENV=production`.