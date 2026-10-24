# VERIFAI Frontend

Next.js 14 (App Router) + TypeScript (strict). Evidence-first opportunity discovery and claim-level verification UI: dark-navy sidebar, white workspace, violet accents. Follows `../docs/frontend_visual_guide.md`, `../docs/verification_policy.md` and `../docs/api.md`.

## Run
```bash
cd frontend
cp .env.example .env.local     # NEXT_PUBLIC_DEMO_MODE=true starts on labelled sample data
npm install
npm run dev                    # http://localhost:3000
```
| Script | Purpose |
|---|---|
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (`next/core-web-vitals`) |
| `npm run build` | Production build |
| `npm run test:e2e` | Playwright journeys (builds and serves the app on :3100; backend intentionally unreachable) |

## Routes
`/explore` Discover · `/opportunities/[id]` detail (Overview, Verification Report, Sources, Similar via `?tab=`) · `/reports/[id]` full report · `/compare` source + opportunity comparison · `/saved` · `/recheck` · `/history` · `/profile` (+ eligibility analysis) · `/checklist`, `/checklist/[id]` · `/passport/[id]` (print / JSON export) · `/notifications` · `/login` · `/dashboard`.

## Sample data vs live data
- All fixtures live in **one module**: `src/lib/dev-fixtures/demo-data.ts`. Organisations are fictional and URLs use the reserved `.example` TLD.
- The sidebar **Sample data** switch (initial value from `NEXT_PUBLIC_DEMO_MODE`, default off) swaps services from the FastAPI client to fixtures. A banner is shown whenever fixtures are active.
- With the switch off nothing is fabricated: an unreachable or unimplemented endpoint produces an error / “not available yet” state.
- To remove fixtures for production, delete `lib/dev-fixtures` and the `demo` branches in `features/*/api.ts` (each is a one-line `if (demo)`).

## Architecture
```
src/app            routes (workspace group has the sidebar shell)
src/components     ui/ layout/ navigation/ opportunities/ verification/ evidence/ comparison/ profile/ history/ checklist/ passport/
src/features       discovery verification saved comparison history matching checklist notifications profile auth compare passport
src/lib            api-client, api-errors, mappers (snake_case → domain), verification (status + coverage rules), date-utils, formatters
src/providers      sample-data, theme, toast
src/types          domain + API contracts
src/styles         tokens, base, components, layout, pages (print rules included)
```
Key rules implemented in code, not just copy:
- `lib/verification.ts` — report status is derived conservatively: a conflict wins; “Verified” needs every core claim (deadline, status, link, eligibility) present **and** confirmed. The coverage score shows its formula and is labelled as not a probability.
- `features/matching/match.ts` — eligibility fit is separate from verification; unknown requirements are never counted as satisfied; no percentage.
- `features/history/diff.ts` — distinguishes no detected changes / confirmed changes / incomplete comparison / source unavailable.
- Run progress (`RunTimeline`, `useRun`) renders only events returned by `GET /api/v1/runs/{id}`; no timers or invented percentages; no cancel button (backend can't cancel).

## Backend integration points
See `../docs/frontend_integration.md`. Secrets (TinyFish, OpenAI, OAuth) never appear in the frontend; only `NEXT_PUBLIC_API_BASE_URL` is read.

## Deploy (Vercel)
Project root `frontend/`, framework Next.js (`vercel.json` included). Set `NEXT_PUBLIC_API_BASE_URL` to the deployed API and `NEXT_PUBLIC_DEMO_MODE=false`. Add the Vercel origin to the backend `FRONTEND_ORIGIN` (CORS, credentials enabled) and use HTTPS callback URLs for OAuth.
