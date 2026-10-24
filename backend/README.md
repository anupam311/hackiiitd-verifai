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