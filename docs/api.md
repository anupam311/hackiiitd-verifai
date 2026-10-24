# VERIFAI API Contract (MVP)

Base URL in development: `http://localhost:8000`. JSON is used for request and response bodies. All user-owned resources require a valid session once authentication is enabled.

## Health
### `GET /health`
Returns `{ "status": "ok", "service": "verifai-api" }`.

## Discovery
### `POST /api/v1/discovery/search`
Request limits (schema defined; the endpoint arrives in a later commit): `query` is required, 1-500 characters; `limit` is 1-50 (default 20); at most 10 `categories` and 10 `fields_of_study`. Category values: `internship`, `scholarship`, `fellowship`, `job`, `research`, `competition`, `other`. Violations return `400 VALIDATION_ERROR`. `state` is one of `queued`, `running`, `completed`, `partial`, `failed`.
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
The production implementation should stream progress using Server-Sent Events or poll `GET /api/v1/runs/{run_id}`.

## Opportunities
- `GET /api/v1/opportunities` — paginated/filterable opportunities.
- `GET /api/v1/opportunities/{opportunity_id}` — normalized opportunity details.
- `GET /api/v1/opportunities/{opportunity_id}/report` — latest verification report and evidence.
- `POST /api/v1/opportunities/{opportunity_id}/recheck` — start a new verification run.
- `GET /api/v1/opportunities/{opportunity_id}/history` — prior snapshots and changes.
- `GET /api/v1/opportunities/{opportunity_id}/sources` — source observations and source comparison.

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