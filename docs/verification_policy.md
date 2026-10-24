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
