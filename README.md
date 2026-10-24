# VERIFAI

Evidence-first opportunity discovery and claim verification.
Verification statuses are assigned by deterministic rules (see `docs/verification_policy.md`).
LLMs only parse and explain; they never decide a status.

## Status: scaffold vs implemented

| Area | State |
|---|---|
| Repo layout and documentation | Implemented |
| Backend: FastAPI app, request IDs, standard error shape, `GET /health` | Implemented |
| Backend: opportunity, source, claim and discovery schemas | Implemented |
| Backend: discovery provider interface + mock adapter | Implemented (real TinyFish adapter pending) |
| Backend: source normalization and de-duplication | Implemented |
| Backend: OpenAI structured extraction (schema-validated, grounded) | Implemented (not yet run against the live API) |
| Backend: claim-level verification engine (deterministic) | Implemented |
| Backend: evidence report and source comparison API (in-memory store until B10) | Implemented |
| Backend: discovery pipeline (provider → extract → verify → report) | Implemented, tested with mock providers only |
| Backend: run progress events (SSE), retries, cancellation, partial results | Implemented |
| Backend: SQLite persistence (opportunities, report snapshots, saved items) | Implemented |
| Backend: recheck with snapshot comparison and history | Implemented, tested with mock providers only |
| Backend: Google sign-in, server-side sessions, logout | Implemented (needs your Google credentials; not yet tried against live Google) |
| Backend: GitHub sign-in, account linking | Not started (B12) |
| Backend: profile and matching | Not started (B13) |
| Frontend: Next.js dashboard | Separate owner (F1-F12) |

`POST /api/v1/discovery/search` returns `503` until a real discovery provider (TinyFish adapter) and LLM credentials are configured. Nothing is simulated.

## Layout

```
Verifai/
├── backend/    FastAPI + Python API
├── frontend/   Next.js + TypeScript app
├── docs/       Architecture, API contract, verification policy, visual guide, commit plan
├── README.md
└── .gitignore
```

## Documentation

`docs/` holds the source-of-truth requirements:
`architecture.md`, `api.md`, `verification_policy.md`, `frontend_visual_guide.md`, `commit_plan.md`, plus `frontend-preview.png` (visual guidance only; its data is not live).

## Configuration

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`.
Never commit real secrets. In production, use the deployment platform's secret manager.

## Development

**Backend** (Python 3.10+):
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload    # http://localhost:8000/health
pytest
```
