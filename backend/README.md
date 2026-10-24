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