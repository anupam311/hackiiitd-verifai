# VERIFAI Architecture

## Design principles
- Evidence before inference: every claim should retain source URL, retrieval time, source type, extracted value, and a short supporting excerpt or locator when permitted.
- Claim-level outcomes: a single opportunity can contain confirmed, partially confirmed, conflicting, unverified, and unavailable claims.
- AI is an assistant, not the authority: LLMs may parse, normalize, and explain; deterministic verification rules assign final statuses.
- Fail safely: inaccessible or stale sources create uncertainty, never automatic proof that an opportunity is closed.
- Provider abstraction: discovery, extraction, LLM, auth, and storage integrations should be replaceable behind small interfaces.

## System components
1. **Next.js client**: Discover/search, opportunity details, evidence report, saved items, profile, source comparison, and recheck/history views.
2. **FastAPI API**: validates requests, enforces authorization, orchestrates workflows, and returns typed response models.
3. **Discovery adapter (TinyFish)**: starts live web discovery/browser tasks and converts provider output to internal source records. Handle rate limits, retries, timeouts, and partial completion. Implemented as the `DiscoveryProvider` protocol (`backend/app/discovery/`). Calls go through `discover_with_policy`, which applies a timeout and bounded exponential backoff to transient errors only; permanent errors are never retried. Only a mock adapter exists so far.
4. **Extraction and reasoning service (OpenAI)**: transforms source text into schema-constrained claims and explains ambiguity. Optional Gemini adapter is evaluated against a benchmark before adoption. Implemented in `backend/app/ai/`. The model returns a strict JSON schema; the output is then validated, each excerpt must appear verbatim in the page text (otherwise the fact is dropped), values are stripped of markup, and the evidence locator is computed by us (`text:start-end` offsets into the whitespace-collapsed page text), not taken from the model. Extraction never assigns verification statuses. The extraction method (`provider:model:prompt_version`) is stored on each fact.
5. **Verification engine**: applies policy rules to evidence, freshness, date parsing, corroboration, and conflicts. Implemented in `backend/app/verification/`. It takes validated evidence (never raw model output) and returns one verdict per claim, each with an explanation, a next step, and per-source roles (supports, discrepant, conflicting, ambiguous). The overall summary is a coverage score with its formula attached, not a probability.
6. **Persistence**: SQLite in the MVP for users, opportunities, source observations, claims, verification runs, snapshots, saved items, and audit events.
7. **Authentication**: Google and GitHub OAuth; validate state/nonce, exchange codes server-side, map provider identities to one internal user, and issue secure sessions.
8. **Testing/observability**: pytest unit/integration tests, Playwright end-to-end flows, structured logs, correlation IDs, and provider-call metrics.

## Request flow
`Search request → TinyFish discovery → source capture → normalize & de-duplicate → extraction → normalized opportunity → claim verification → report persistence → frontend report`

For recheck:
`Saved opportunity → fetch current sources → new snapshot → compare normalized claims → mark changes/conflicts → persist run → history UI`

**Reports.** A verification run produces one `VerificationReport` snapshot (claims, evidence with source attribution, sources). The source comparison is derived from the stored report, not stored separately, so the two cannot disagree.

## Core entities
- `User`: id, email, display name, avatar URL, created_at
- `OAuthIdentity`: user_id, provider (`google` or `github`), provider_subject
- `Opportunity`: id, title, organization, category, location, canonical_url, deadline, status, created_at, updated_at
- `SourceObservation`: id, opportunity_id, url, domain, source_type, retrieved_at, http_status, content_hash, freshness
- `Claim`: id, opportunity_id, claim_type, normalized_value, status, explanation
- `ClaimEvidence`: claim_id, source_observation_id, extracted_value, excerpt, confidence, evidence_locator
- `VerificationRun`: id, opportunity_id, started_at, completed_at, state, overall_score, summary
- `ClaimSnapshot`: run_id, claim_id, normalized_value, status
- `SavedOpportunity`: user_id, opportunity_id, saved_at
- `AuditEvent`: actor_id, event_type, entity_id, created_at, metadata

Implemented schema additions (see `backend/app/schemas/`):
- `Opportunity`: `is_demo` flag; `deadline` is a `DeadlineInfo` (raw text, optional parsed date, timezone, `is_certain`); `status` defaults to `unknown`
- `SourceObservation`: `retrieval_outcome` (`ok`, `not_found`, `blocked`, `http_error`, `timeout`, `unknown`)
- `Claim`: `checked_at`
- `ClaimEvidence`: `extraction_method`, `schema_version`; `confidence` is extraction confidence, not source credibility

## Verification status model
- `confirmed`: evidence from an authoritative or sufficiently corroborated source supports the claim.
- `partially_confirmed`: evidence supports part of the claim or key details remain ambiguous.
- `conflicting`: credible sources disagree materially.
- `unverified`: there is insufficient evidence to establish the claim.
- `unavailable`: the claim could not be evaluated because required evidence was inaccessible or absent.

Do not calculate an overall score as if it were a probability unless calibrated and validated. In the MVP, display a transparent completeness/consistency score with a clear explanation of its formula.

## Deployment topology
- Vercel: Next.js frontend.
- Python-compatible host: FastAPI backend and background worker if needed.
- Managed database later: PostgreSQL.
- Secrets live in deployment secret managers, never in browser bundles.
