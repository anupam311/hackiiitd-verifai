# VERIFAI

Evidence-first opportunity discovery and claim verification.
Verification statuses are assigned by deterministic rules (see `docs/verification_policy.md`).
LLMs only parse and explain; they never decide a status.

## Status: scaffold vs implemented

| Area | State |
|---|---|
| Repo layout and documentation | Implemented |
| FastAPI backend (health, error shape) | Not started (commit 2) |
| Next.js dashboard | Not started (commit 3) |
| TinyFish discovery | Not started (commit 7) |
| OpenAI extraction | Not started (commit 9) |
| Verification engine | Not started (commit 10) |
| SQLite persistence | Not started (commit 14) |
| Google / GitHub OAuth | Not started (commits 15-16) |

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

Setup instructions for each side are added in the commit that creates it.