# Frontend Visual Guide

## Visual direction
A polished, evidence-first SaaS dashboard: deep navy navigation rail, light neutral workspace, white cards, subtle borders, restrained purple primary actions, green confirmed indicators, amber partial indicators, red conflicts, and muted gray unknown/unavailable states. Use compact but readable typography, consistent spacing, rounded cards, and clear visual hierarchy.

The file `frontend-preview.png` is a generated visual reference. It illustrates intended layout and hierarchy only; its sample opportunities, dates, counts, and percentages are not live results.

## Primary screens
1. **Discover** — sidebar navigation; search field; filters for category, location, field of study, deadline, level, and more; result count and sorting; opportunity cards with organization, location, tags, deadline, and explainable match score.
2. **Opportunity detail** — title and organization; open/closed/unknown state with source and timestamp; tabs for Overview, Verification Report, Sources, and Similar Opportunities; Save and Recheck actions.
3. **Verification report** — overall summary with a transparent formula; claim-by-claim table; each row includes claim, source finding, status, explanation, and evidence link.
4. **Evidence sources** — official source prioritized, source type and retrieved time visible; source comparison; contradiction callouts and stale-source warnings.
5. **Saved opportunities** — searchable saved list with latest verification state and quick recheck.
6. **Profile** — education, location, experience, interests, and preference fields; never require more personal data than matching needs.
7. **Compare sources** — aligned claims by source; make agreement, partial agreement, conflicts, and missing values visually distinct.
8. **Recheck & history** — select an opportunity, run recheck, view actual progress, and compare past snapshots.
9. **Authentication** — clear “Continue with Google” and “Continue with GitHub” options; disclose account linking and logout.

## Interaction states
Every data-backed view needs loading, empty, partial, error, and stale states. Run progress must reflect backend events, not fabricated animation. Buttons need disabled/in-progress states and accessible labels. Provide keyboard navigation, visible focus rings, semantic headings, and mobile layouts.

## Status language
- Confirmed — evidence supports the claim.
- Partially confirmed — only part of the claim is supported or ambiguity remains.
- Conflicting — credible sources disagree.
- Unverified — evidence is insufficient.
- Unavailable — the claim could not be evaluated.

## Responsive behavior
Desktop: persistent sidebar and multi-column dashboard. Tablet: narrower sidebar or collapsible navigation. Mobile: single-column cards, stacked evidence tables, and horizontally scrollable comparison sections with accessible labels.
