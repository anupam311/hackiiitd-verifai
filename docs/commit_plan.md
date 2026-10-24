# 20-Commit Implementation Plan

Each commit should be small, runnable, and reviewable. Suggested messages are listed in dependency order.

1. `chore: scaffold monorepo and developer documentation` — repo layout, README, env template, docs.
2. `feat(api): add FastAPI app and health endpoint` — app factory, config, health test.
3. `feat(frontend): initialize Next.js TypeScript dashboard shell` — app router, global styles, navigation.
4. `feat(ui): build discover search and filter controls` — accessible search, filters, empty/loading states.
5. `feat(ui): add opportunity cards and explainable match badges` — use clearly labeled demo fixtures only.
6. `feat(api): define opportunity and source schemas` — Pydantic models and validation.
7. `feat(discovery): add TinyFish provider interface` — interface, timeout/error model, mock adapter for tests.
8. `feat(discovery): normalize live source observations` — URLs, timestamps, source metadata, deduplication.
9. `feat(ai): add OpenAI structured extraction service` — schema validation and prompt versioning.
10. `feat(verification): implement claim-level policy engine` — status rules, date parsing, conflicts, freshness.
11. `feat(report): expose evidence report API and detail UI` — claim table, source evidence, uncertainty explanations.
12. `feat(sources): add source comparison and conflict callouts` — cross-source comparison with citations/links.
13. `feat(runs): add progress events and partial results` — run states, SSE/polling, retries and cancellation policy.
14. `feat(saved): persist saved opportunities and recheck history` — SQLite repositories and snapshot diffing.
15. `feat(auth): add Google OAuth login flow` — state/nonce validation and secure session.
16. `feat(auth): add GitHub OAuth login flow` — provider identity mapping and account-linking safeguards.
17. `feat(profile): add profile editing and explainable matching` — profile data minimization and match reasons.
18. `test: add pytest policy coverage and Playwright journeys` — unit, integration, and core e2e tests.
19. `chore(deploy): configure production settings and deployment docs` — Vercel/backend host, CORS, secrets, health checks.
20. `test: harden errors, accessibility, security, and release checklist` — failure cases, keyboard/accessibility pass, final docs.

## Definition of done
- No unlabelled demo data presented as live.
- Verification statuses follow `verification_policy.md`.
- All API errors use the documented shape.
- Google and GitHub OAuth flows have security tests and provider credentials configured only in deployment secrets.
- `pytest` and Playwright pass for supported environments.
- README clearly distinguishes scaffold from implemented integrations.
