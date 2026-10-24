# Verification Policy

## Purpose
VERIFAI evaluates individual claims using traceable, time-stamped evidence. It does not guarantee that an opportunity is legitimate or that information will remain unchanged after retrieval.

## Claim types
Deadline, application status, application URL, eligibility, stipend/compensation, location, duration, start date, organization, and other structured attributes.

## Evidence requirements
For every observation retain:
- source URL and domain
- retrieval timestamp in UTC
- source category (official, employer, institution, aggregator, community, other)
- extracted value and normalized value
- supporting excerpt or locator when allowed
- extraction method/model and schema version
- freshness assessment and retrieval outcome

Prefer official organization or institution pages. Aggregators and community pages can provide discovery leads or corroboration but should not silently override authoritative evidence.

## Status definitions
- **Confirmed**: authoritative evidence or sufficient independent corroboration supports the normalized claim and no material unresolved contradiction remains.
- **Partially confirmed**: some elements are supported, but a subfield, scope, date, or condition remains ambiguous.
- **Conflicting**: credible sources contain materially different values that cannot be reconciled.
- **Unverified**: evidence is insufficient to establish or refute the claim.
- **Unavailable**: the system could not evaluate the claim because required source content was missing or inaccessible.

## Critical safeguards
1. A failed request, timeout, blocked page, CAPTCHA, robots restriction, or missing page is not evidence that an opportunity is closed.
2. A deadline in the past does not by itself prove applications are closed; rolling applications, extensions, timezone differences, and stale listings are possible.
3. Do not infer a deadline year when ambiguous. Preserve the original text and mark the normalized date uncertain.
4. Do not treat a search result snippet as equivalent to inspecting the destination page.
5. Conflicting stipend, eligibility, or deadline values must remain visible with source attribution.
6. Never fabricate a source, excerpt, retrieval time, confidence score, or live result.
7. Distinguish source credibility from extraction confidence; a high-confidence extraction from a weak source is still weak evidence.
8. Recheck results must compare snapshots and identify which claims changed, disappeared, or became stale.
9. LLM output is untrusted input: validate schema, sanitize display, and apply deterministic policy rules.
10. The overall summary must be explainable and must not be described as a probability unless empirically calibrated.

## Freshness guidance
Freshness thresholds should vary by claim type and opportunity category. Application status and deadlines can change quickly; identify old observations as stale and recheck before making strong claims. Display timestamps in the user's locale while storing UTC.

## Score guidance
For an MVP, prefer “verification coverage/consistency” rather than an uncalibrated “truth probability.” If a percentage is shown, document the formula and distinguish missing evidence from contradictions. Never imply that a score guarantees authenticity.

## User-facing explanation
Each status should include a concise reason, sources used, last checked time, and a next step when useful (e.g., open official page or recheck). Encourage users to confirm critical details on the official page before applying.

## Implementation notes (backend)
- Deadlines are stored as `DeadlineInfo`: the original text is always kept, a date is only set when unambiguous, and `is_certain` requires a parsed date (safeguard 3).
- `Opportunity.status` defaults to `unknown`.
- Evidence requires a locator and records the extraction method and schema version.
- `official` is never inferred from a domain alone. Known aggregator and community domains are always classified as such, even if a provider hints otherwise.
- Failed retrievals (404, 403, 429, 5xx, timeouts) are stored as observations with an outcome and `unknown` freshness. They are never evidence that an opportunity is closed (safeguard 1).
- A later failed fetch of a URL does not replace an earlier successful observation.
- Observation freshness uses a 7-day default; per-claim thresholds are defined with the verification engine (B7).
- Observations with naive or future timestamps are rejected.
- Extracted values are only accepted when their excerpt is found verbatim in the retrieved page; otherwise they are dropped and counted (safeguards 6 and 9).
- Page text is treated as untrusted data in the prompt, and the prompt delimiter is removed from page text so it cannot close the data block.
- Pages longer than 30,000 characters are truncated and flagged; at most 30 facts are accepted per page.
- Invalid, refused or truncated model output fails that source's extraction. It is never retried and never guessed.
- Recheck comparison (safeguard 8): claims are reported as `changed`, `appeared`, `disappeared` or `became_stale`. A claim that went from evidence-backed to `unavailable` is flagged as "evidence unavailable", never as "information changed". Staleness with an unchanged value is reported as `became_stale`, not as a value change.
- Older snapshots are immutable, so before/after comparisons stay reproducible.

## Decision rules (as implemented)

**Source authority.** `official`, `employer` and `institution` sources are authoritative. `aggregator`, `community` and `other` are not.

**Evidence that counts.** Only evidence from successfully retrieved sources with a normalizable value and extraction confidence of at least 0.5. Anything else is kept as `ambiguous` and shown, but never decides a status.

**Status by case**
| Situation | Status |
|---|---|
| No readable source states the claim (including failed or blocked retrievals) | unavailable |
| Fresh authoritative evidence, one agreed value | confirmed (differing non-authoritative values stay visible as discrepancies) |
| Authoritative evidence agrees but is older than the claim's freshness window | partially confirmed, flagged stale |
| Authoritative sources disagree (structured claims or location/organization) | conflicting |
| Authoritative sources word eligibility/other claims differently | partially confirmed, needs review (free text is never auto-declared conflicting) |
| Authoritative source mentions the claim but the value is ambiguous | partially confirmed |
| Only non-authoritative sources, 2+ domains agree | partially confirmed (never confirmed: independence is not established) |
| Only non-authoritative sources, one source | unverified |
| Non-authoritative sources disagree | conflicting |
| Only ambiguous or low-confidence evidence, no authoritative source | unverified |

**Freshness windows (days):** application status 2, deadline 7, application URL 14, eligibility 30, stipend 30, duration 30, start date 30, location 60, organization 180, other 30.

**Opportunity status.** `open` or `closed` is set only by a confirmed `application_status` claim. A past deadline or a failed fetch never closes an opportunity; a past deadline adds a note instead.

**Known limits.** Aliases such as Bangalore/Bengaluru are not resolved and show as differences. Timezone abbreviations such as IST are not interpreted. Only English month names are parsed. Date ranges and multiple different dates stay ambiguous.

**Score.** Coverage score = 100 x (confirmed x 1 + partially confirmed x 0.5) / claims evaluated. Conflicting, unverified and unavailable claims score 0. It is not a probability.