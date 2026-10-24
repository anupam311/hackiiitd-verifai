# Implementation Prompt — VERIFAI

You are implementing VERIFAI, an evidence-first opportunity discovery and claim verification application. Follow `docs/architecture.md`, `docs/api.md`, `docs/verification_policy.md`, and `docs/frontend_visual_guide.md` as source-of-truth requirements.

## Required stack
- Next.js App Router + TypeScript for frontend.
- FastAPI + Python for backend.
- TinyFish for live web discovery/browser interaction, behind a provider adapter.
- OpenAI API as the primary LLM for schema-constrained extraction and ambiguity explanations.
- Gemini is optional and must not be added to the critical path unless evaluation demonstrates a clear quality/cost benefit.
- SQLite for MVP persistence.
- Google OAuth and GitHub OAuth for signup/signin.
- pytest and Playwright.
- GitHub source control; Vercel frontend and Python-compatible backend deployment.

## Product requirements
1. Build a responsive dashboard inspired by `docs/frontend-preview.png`; use it as visual guidance, not as a source of factual opportunity data.
2. Include Discover, Saved, Recheck, History, Profile, Notifications, and theme controls.
3. Search opportunities by natural language and filters: category, location, field of study, deadline, level, and additional filters.
4. Show match explanations and matched/unmatched/unknown profile requirements.
5. Detail view must include Overview, Verification Report, Sources, and Similar Opportunities.
6. Every claim must have its own status, evidence sources, timestamp, and explanation.
7. Compare source findings side-by-side and make contradictions visible.
8. Show live run progress, retries, elapsed time, partial results, and meaningful failure states based on actual backend events.
9. Support save/unsave, recheck, run history, and before/after claim comparisons.
10. Implement Google and GitHub OAuth safely. Keep secrets server-side; validate state/nonce; use secure HTTP-only sessions; provide logout.
11. Build automated tests for parsing, verification statuses, conflicts, stale evidence, auth boundaries, and key user journeys.

## Engineering rules
- Use typed request/response schemas and explicit service boundaries.
- Never hard-code realistic live opportunities, scores, source findings, or dates as if verified. Seed/demo data must be clearly labeled.
- Never mark an opportunity closed merely because a page request failed, a deadline is in the past, or sources are unavailable.
- AI outputs are untrusted until validated against schemas and verification rules.
- Store source URL, retrieved_at, source type, and evidence locator for each observation.
- Use deterministic date parsing with timezone awareness; ambiguous dates remain partially confirmed or unverified.
- Add retries with exponential backoff only for transient provider failures, with bounded attempts and timeouts.
- Avoid logging secrets, tokens, full personal profiles, or unnecessary page contents.
- Keep UI accessible: keyboard navigation, visible focus, semantic labels, contrast, and loading/empty/error states.
- Keep modules small and documented; avoid speculative microservices.

## Delivery sequence
Follow `docs/commit_plan.md`. Finish the live discovery → official-source inspection → claim verification → evidence report workflow before polishing optional features. Run backend tests and frontend checks before declaring a milestone complete. Update docs when API behavior changes.
