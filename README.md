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
| Backend: report and source comparison API | Not started (B8) |
| Backend: run progress events | Not started (B9) |
| Backend: SQLite persistence | Not started (B10) |
| Backend: Google / GitHub OAuth | Not started (B11-B12) |
| Backend: profile and matching | Not started (B13) |
| Frontend: Next.js dashboard | Separate owner (F1-F12) |

Nothing here presents live opportunity data yet. Any future demo fixtures will be clearly labeled as demo data.

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
