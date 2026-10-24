# Environment Setup

## Requirements
- Node.js LTS and npm
- Python 3.11+
- Git
- Provider credentials only when implementing live integrations

## Local setup
1. Copy `.env.example` to `.env` at the repository root and fill only the values needed for your current milestone.
2. Start backend:
   ```bash
   cd backend
   python -m venv .venv
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
3. Start frontend in a second terminal:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Visit `http://localhost:3000` and `http://localhost:8000/health`.

## Provider configuration
- **TinyFish**: obtain API access and confirm the current API endpoint, auth scheme, rate limits, and allowed use from its official documentation. Implement the provider behind `DiscoveryProvider`; do not guess endpoints.
- **OpenAI**: set `OPENAI_API_KEY` and a supported model name. Keep calls server-side and validate structured output.
- **Gemini (optional)**: configure only if running a documented comparison/evaluation.
- **Google OAuth**: configure authorized origin `http://localhost:3000` as appropriate and callback `http://localhost:8000/auth/google/callback` in the provider console.
- **GitHub OAuth**: set homepage URL and callback `http://localhost:8000/auth/github/callback` in the OAuth app settings.
- Ensure frontend origin and backend CORS allow-list agree. In production, use HTTPS and exact deployed callback URLs.

## Secret handling
- Never commit `.env`, OAuth client secrets, API keys, session secrets, or provider tokens.
- Rotate any secret that was accidentally committed.
- Do not prefix secrets with `NEXT_PUBLIC_`; that prefix exposes values to the browser.
- Use a secret manager in deployment.
- Set a long random `SESSION_SECRET`; use secure cookies in production.

## Deployment outline
- Deploy `frontend/` to Vercel with `NEXT_PUBLIC_API_BASE_URL`.
- Deploy `backend/` to a Python-compatible host with secrets, HTTPS, persistent database storage, health checks, and configured CORS.
- SQLite is suitable for a local/demo MVP; confirm filesystem persistence and concurrency constraints before production. Move to PostgreSQL for robust multi-instance deployment.
