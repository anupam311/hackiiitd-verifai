# Deployment Guide

## Architecture

```
Browser ──→ Vercel (Next.js) ──→ /api proxy → FastAPI backend
                                └─→ /auth proxy → FastAPI backend
FastAPI ──→ SQLite (MVP) / PostgreSQL (production)
        ──→ TinyFish API  (discovery, when configured)
        ──→ OpenAI API    (extraction, when configured)
        ──→ Google / GitHub OAuth
```

## Environment variables

All server-side secrets live in your deployment secret manager. **Never commit `.env` or put secrets in `NEXT_PUBLIC_*` variables (those are bundled into the client).**

### Backend (FastAPI)

| Variable | Required | Notes |
|---|---|---|
| `VERIFAI_ENV` | no | `production` disables `/docs` and `/openapi.json` |
| `VERIFAI_LOG_LEVEL` | no | `INFO` (default) |
| `VERIFAI_DATABASE_URL` | no | `sqlite:///./verifai.db` (default); use an absolute path in production |
| `VERIFAI_SESSION_SECRET` | **yes** | Long random string (≥32 chars); rotate if leaked |
| `VERIFAI_CORS_ORIGINS` | **yes** | Comma-separated or JSON list of allowed browser origins, e.g. `https://app.example.com` |
| `VERIFAI_PUBLIC_BASE_URL` | **yes** | Where the API is reachable from the browser (builds OAuth redirect URIs), e.g. `https://api.example.com` |
| `VERIFAI_FRONTEND_URL` | **yes** | Where users land after sign-in, e.g. `https://app.example.com` |
| `VERIFAI_SESSION_TTL_DAYS` | no | `7` (default) |
| `VERIFAI_TRUSTED_HOSTS` | no | Comma-separated list of allowed `Host` values (e.g. `api.example.com`). Empty = disabled. |
| `VERIFAI_MAX_REQUEST_BODY_BYTES` | no | `1048576` (1 MB default) |
| `OPENAI_API_KEY` | no* | Required for extraction |
| `OPENAI_MODEL` | no* | Required for extraction |
| `GOOGLE_OAUTH_CLIENT_ID` | no* | Required for Google sign-in |
| `GOOGLE_OAUTH_CLIENT_SECRET` | no* | Required for Google sign-in |
| `GITHUB_OAUTH_CLIENT_ID` | no* | Required for GitHub sign-in |
| `GITHUB_OAUTH_CLIENT_SECRET` | no* | Required for GitHub sign-in |
| `TINYFISH_API_KEY` | no* | Required for live discovery |

*These are optional at startup; missing values disable the related feature with a `503` error at runtime.

### Frontend (Next.js)

| Variable | Notes |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of the FastAPI backend as seen by the browser (e.g. `https://api.example.com`) |

## Production checklist

Run through this before every production release:

### Security
- [ ] `VERIFAI_ENV=production` is set (disables `/docs` and `/openapi.json`)
- [ ] `VERIFAI_SESSION_SECRET` is set to a strong random value (not the default)
- [ ] `VERIFAI_CORS_ORIGINS` is set to the exact frontend origin(s) — no wildcards
- [ ] `VERIFAI_PUBLIC_BASE_URL` uses `https://` (enables `Secure` on session cookies)
- [ ] `VERIFAI_TRUSTED_HOSTS` is set to the API's own hostname(s)
- [ ] OAuth callback URLs in Google/GitHub console match `VERIFAI_PUBLIC_BASE_URL`
- [ ] No secrets in environment variables prefixed with `NEXT_PUBLIC_`
- [ ] No `.env` files committed to the repository
- [ ] All API keys rotated if any were accidentally committed

### Application
- [ ] `GET /health` returns `200` after deploy
- [ ] `GET /health/ready` returns `200` (DB is reachable)
- [ ] `/docs` returns `404` (disabled in production)
- [ ] Google sign-in flow works end-to-end: login → callback → `/auth/me`
- [ ] GitHub sign-in flow works end-to-end
- [ ] `POST /auth/logout` clears the session
- [ ] Discovery search returns `503` when TinyFish is not configured (not `500`)
- [ ] Error responses match the documented shape `{"error": {code, message, request_id}}`
- [ ] `X-Request-ID` header present on every response

### Database
- [ ] `VERIFAI_DATABASE_URL` points to a persistent volume (not `/tmp`)
- [ ] The database file is included in backups
- [ ] SQLite WAL mode is confirmed if using high-concurrency writes (future: migrate to PostgreSQL)

### Infrastructure
- [ ] HTTPS is terminated at the load balancer or reverse proxy
- [ ] Health check path `/health` is configured on the load balancer (use `/health/ready` for readiness)
- [ ] Response size / body size limits are set at the reverse proxy layer as well
- [ ] Structured logs are collected (the app logs in plaintext; use a log shipper if needed)

## Running the backend

```bash
# Development
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1      # PowerShell (Windows)
# source .venv/bin/activate     # bash (macOS/Linux)
pip install -r requirements.txt
uvicorn app.main:app --reload

# Production (example with gunicorn + uvicorn workers)
pip install gunicorn
gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

> **SQLite and multiple workers**: SQLite WAL mode handles concurrent reads well, but write throughput is limited to one writer at a time. For the MVP, 1–2 workers on a single machine is fine. Migrate to PostgreSQL before running multiple replicas or if write latency becomes an issue.

## Vercel deployment (frontend)

1. Connect the repository to Vercel.
2. Set the root directory to `frontend/`.
3. Add `NEXT_PUBLIC_API_BASE_URL` pointing to the deployed backend.
4. Set up `/api` and `/auth` rewrites in `next.config.js` to proxy to the backend (required so the session cookie is same-site).

```js
// frontend/next.config.js (example)
const API = process.env.NEXT_PUBLIC_API_BASE_URL;
module.exports = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/auth/:path*", destination: `${API}/auth/:path*` },
    ];
  },
};
```

## Health checks

| Endpoint | Purpose | Expected |
|---|---|---|
| `GET /health` | Liveness (always fast) | `200 {"status":"ok","service":"verifai-api","version":"..."}` |
| `GET /health/ready` | Readiness (checks DB) | `200 {"status":"ready",...}` or `503` |

Configure your load balancer:
- **Liveness**: `/health` — restart the container if this fails.
- **Readiness**: `/health/ready` — remove from rotation until this succeeds.
