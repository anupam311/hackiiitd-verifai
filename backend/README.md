# Backend

FastAPI + Python API for VERIFAI. Requires Python 3.11+ (the TinyFish SDK needs it).

## Run and test
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload    # http://localhost:8000/health
pytest
```
Interactive API docs are at `/docs` in development and are disabled when `VERIFAI_ENV=production`.

## Configuration
Settings are read from `VERIFAI_*` environment variables (or `backend/.env`). See `.env.example`.

## Layout
```
backend/
├── app/
│   ├── main.py      app factory, CORS, request-ID middleware
│   ├── config.py    settings
│   ├── errors.py    standard error shape and handlers
│   └── routes/      HTTP routes (health so far)
└── tests/
```

## Error handling
Every error response uses the shape in `docs/api.md` and carries an `X-Request-ID` header. Validation errors never echo the submitted input, and unexpected errors never expose exception details.

HTTP 422 (Pydantic's default for body validation errors) is re-mapped to **400 VALIDATION_ERROR** so callers never need to handle two different status codes for invalid input.

## Production settings
See `docs/deployment.md` for the full deployment guide and production checklist.

Key production features (all implemented in `app/main.py` and `app/config.py`):

- **Security response headers** on every response: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- **Auth no-cache headers**: `/auth/*` responses always include `Cache-Control: no-store` so tokens are never cached by browsers or proxies.
- **TrustedHostMiddleware**: enabled when `VERIFAI_TRUSTED_HOSTS` is set. Rejects requests with an unexpected `Host` header with `400`.
- **Body-size guard**: rejects any request whose `Content-Length` exceeds `VERIFAI_MAX_REQUEST_BODY_BYTES` (default 1 MB) with `413 PAYLOAD_TOO_LARGE` before reading the body.
- **`/health/ready`** readiness probe: verifies the DB is reachable. Use this (not `/health`) as the load-balancer readiness check.
- **Startup log summary**: logs active integrations at INFO level without exposing any secret values.
- **`VERIFAI_ENV=production`**: disables `/docs` and `/openapi.json`.



## Schemas (`app/schemas/`)
- `enums.py`: categories, source types, retrieval outcomes, freshness, claim types, verification statuses, run states
- `opportunity.py`: `Opportunity`, `DeadlineInfo`
- `source.py`: `SourceObservation`
- `claim.py`: `Claim`, `ClaimEvidence`
- `discovery.py`: `DiscoverySearchRequest`, `DiscoverySearchResponse`

Validation enforces: http(s) URLs only; timezone-aware datetimes, stored in UTC; an observation's domain must match its URL host; a certain deadline needs a parsed date; every claim needs an explanation; every piece of evidence needs a locator. `Opportunity.is_demo` marks demo data.

## Discovery providers (`app/discovery/`)
- `base.py`: `DiscoveryProvider` protocol, `RawSourceRecord`, `DiscoveryResult`
- `errors.py`: `ProviderError` and subclasses; each is transient (retryable) or permanent
- `retry.py`: `discover_with_policy`, with a per-call timeout and bounded exponential backoff for transient errors only
- `mock.py`: scriptable provider for tests (contains no data of its own)
- `tinyfish.py`: the real TinyFish adapter (see below)

## TinyFish discovery (`app/discovery/tinyfish.py`)
Ported from the `radar.py` workshop script. `discover` = radar stage 3 (Search finds pages) + stage 2 (one agent per page, in parallel, same output schema); `VERIFAI_TINYFISH_SEED_PAGES` adds fixed careers pages like radar's `PAGES`; `VERIFAI_TINYFISH_STEALTH=true` is radar's `BrowserProfile.STEALTH`.

**Setup:** `pip install -e ".[dev]"` (installs the `tinyfish` SDK), then set `TINYFISH_API_KEY` in `backend/.env`. Discovery also needs `OPENAI_API_KEY` + `OPENAI_MODEL` because every source goes through extraction. Without the key (or the SDK) the API still starts and `/api/v1/discovery/search` answers `503`.

**How it plugs in**
- One `RawSourceRecord` per listing the agent reports. Its URL is the listing's own apply link; its text is a plain-text rendering of what the agent reported. That text is then extracted by the LLM and verified by the normal rules.
- Agent output is untrusted: markup and control characters are stripped, lengths capped, wrong types dropped. Listings with no title, no link of their own, or a link shared with other listings are skipped and counted in a warning.
- The adapter never sets a source type, so TinyFish results are never "official". A single such source cannot confirm a claim or mark an opportunity open/closed.
- Failures are not closures: an unreadable page is a warning (discover) or an observation with no content (recheck, so its claims become `unavailable`).
- Errors map to `Provider*`: 401/403 and a missing SDK/key fail the run; 429/5xx/timeouts are retried (at most 2 attempts, since each run costs credits). If every page fails the call raises; if only some fail the result is partial.
- Agent runs are slow, so a TinyFish-specific `RetryPolicy` (call timeout derived from page count, concurrency and per-page timeout) replaces the 30 s default.
- Limits: `VERIFAI_TINYFISH_MAX_PAGES` (default 5), `_MAX_CONCURRENCY` (3), `_AGENT_TIMEOUT_S` (240). Search is free; each agent run costs credits.

**Known limitation:** the evidence text is the agent's report of the page, not raw page HTML, so excerpts are grounded in that report. Recheck re-runs an agent on each listing URL.

## Normalization (`app/discovery/normalize.py`)
Raw provider records become `SourceObservation`s: URLs are canonicalized (host lowercased; fragment, credentials, default ports and tracking parameters removed), timestamps are converted to UTC, outcomes are derived from the HTTP status, freshness is computed, and duplicates are removed per canonical URL. Invalid records are rejected with a reason only (their URLs are not stored). Source-type and failure rules are in `docs/verification_policy.md`.

## AI extraction (`app/ai/`)
- `prompts.py`: versioned prompt (`PROMPT_VERSION`) and schema version. Page text is passed as data between `<page_content>` tags.
- `models.py`: strict-compatible wire schema (what the model returns) and validated `ExtractedFact`
- `client.py`: `LLMClient` protocol, `OpenAIClient`, bounded retry for transient errors only
- `extraction.py`: `extract_from_text` validates, grounds and sanitizes model output

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `backend/.env` (no default model is assumed). Tests use fake clients and never call the network.

## Verification engine (`app/verification/`)
- `dates.py`: deterministic date parsing (never guesses a year, day/month order, or which of several dates applies)
- `normalizers.py`: per-claim-type normalization (dates, status, URL, stipend, duration, free text)
- `policy.py`: `verify_claim` / `verify_opportunity` assign one status per claim; `summarize` computes the coverage score; `derive_opportunity_status` is the only place an opportunity becomes open or closed
- `models.py`: `EvidenceItem` (input) and `ClaimVerdict` (output)

No LLM is used here. The rules are documented in `docs/verification_policy.md`.

## Reports and comparison (`app/report/`)
- `models.py`: `VerificationReport` (claims with evidence and sources) and `SourceComparison` (per-claim rows across sources, conflict callouts, warnings)
- `builder.py`: pure functions that assemble both from verifier output
- `app/repositories/`: `Store` protocol and `SqliteStore` (stdlib `sqlite3`)

## Runs (`app/runs/`)
- `manager.py`: in-process run registry with event log, cancellation, a cap on active runs, and eviction of old finished runs
- `pipeline.py`: `run_discovery` runs provider → normalize → extract → group → verify → report → store, emitting an event at each real step
- Routes: `app/routes/discovery.py` (starts a run) and `app/routes/runs.py` (status, SSE events, cancel)

Run state is in memory and lost on restart; reports, opportunities and saved items are persisted in SQLite.

When testing the API with runs, use `with TestClient(app) as client:` so one event loop stays alive for the background task.

## Persistence and history
`SqliteStore` keeps opportunities, report snapshots (stored as JSON) and saved items. The database path comes from `VERIFAI_DATABASE_URL` (default `sqlite:///./verifai.db`; `sqlite:///:memory:` for tests). Every verification or recheck run adds a new snapshot; old snapshots are never modified. `app/report/diff.py` compares two snapshots (changed, appeared, disappeared, became stale).

`saved` and `recheck` routes use `current_user_id` from `app/auth/deps.py`.

Tests set `VERIFAI_DATABASE_URL` to an in-memory database in `tests/conftest.py`.

## Authentication (`app/auth/`, `app/routes/auth.py`)
Sign in with Google uses the OpenID Connect authorization-code flow with PKCE, a one-time `state` bound to the browser by a cookie, and a `nonce` checked inside the verified ID token.

**Set up Google:** Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web application). Add the redirect URI `http://localhost:8000/auth/google/callback`. Put the client ID and secret in `backend/.env` as `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`. Without both, `/auth/google/login` returns `503`.

**Try it:** with the API running, open `http://localhost:8000/auth/google/login` in a browser. After signing in you are redirected to `VERIFAI_FRONTEND_URL` (the page may not exist yet). Then open `http://localhost:8000/auth/me` to see your session. Browsers share cookies across ports on `localhost`.

**Security properties**
- Client secret and tokens stay server-side. The browser never sees them, and responses and logs never include them.
- The ID token's RS256 signature is checked against Google's published keys, along with issuer, audience, expiry and nonce. Other algorithms (`none`, HS256) are rejected.
- Sessions are random 256-bit tokens in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` whenever `VERIFAI_PUBLIC_BASE_URL` is https). Only the SHA-256 hash is stored, so logout and expiry take effect on the server, and a copied cookie stops working.
- A new session is issued on every sign-in (no session fixation). Sessions last `VERIFAI_SESSION_TTL_DAYS` (default 7).
- After sign-in only same-site relative paths are accepted for `next` (no open redirects). Errors redirect to `/login?error=<code>` using a fixed set of codes.
- Browser requests with a cross-site `Origin` header on `POST/PUT/PATCH/DELETE` get `403`.
- An email is stored only if Google marks it verified.

**Set up GitHub:** GitHub → Settings → Developer settings → OAuth Apps → New OAuth App. Set the callback URL to `http://localhost:8000/auth/github/callback`. Put the client ID and secret in `backend/.env` as `GITHUB_OAUTH_CLIENT_ID` and `GITHUB_OAUTH_CLIENT_SECRET`. Without both, `/auth/github/login` returns `503`.

GitHub does not issue OIDC ID tokens, so there is no JWT to verify. Instead:
- The authorization code is exchanged for an access token server-side via `POST https://github.com/login/oauth/access_token`.
- The stable numeric user ID is fetched from `GET https://api.github.com/user`.
- The primary verified email is fetched from `GET https://api.github.com/user/emails`.
- PKCE code challenge is stored in the DB; the verifier is sent to GitHub's token endpoint.

**Account linking:** if a GitHub login presents a verified email that matches an existing verified-email user (e.g. already signed in with Google), the GitHub identity is linked to that account rather than creating a duplicate. Unverified emails are never used for linking.

## Profile API (`app/routes/profile.py`)
The profile stores a small set of user preferences (education, location, experience_years, interests) to power explainable matching.

- `GET /api/v1/profile` — returns the current user's profile (all fields default to null/empty).
- `PATCH /api/v1/profile` — partial update. Unspecified fields are preserved. Interests are deduplicated (case-insensitive) and capped at 10. Requires a valid session.
- `GET /api/v1/profile/match/{opportunity_id}` — returns explainable match reasons (location, interests, experience). **Data-minimization:** raw profile values are never included in the response; only human-readable labels are returned.

Profile data is stored as a JSON blob per user in the `profiles` table. It is never included in search results or shared with other users.

## Testing (`app/repositories/memory.py`)
`InMemoryStore` implements the full `Store` protocol without any filesystem or SQLite dependency. It is used in tests that need isolation from the database. It is thread-safe but not suitable for production (no persistence, no FK enforcement). All auth methods (sessions, OAuth state, user management, account linking) and profile methods are implemented.
