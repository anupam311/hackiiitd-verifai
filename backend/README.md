# Backend

FastAPI + Python API for VERIFAI. Requires Python 3.10+.

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

A real TinyFish adapter is not implemented yet. It must implement `DiscoveryProvider`, set `retrieved_at` at fetch time, and raise the `Provider*` errors.

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