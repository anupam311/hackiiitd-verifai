"""Profile API and explainable matching.

GET  /api/v1/profile         — authenticated user's profile
PATCH /api/v1/profile        — update profile (partial update; unspecified fields are unchanged)
GET  /api/v1/profile/match/{opportunity_id}
                             — explainable match reasons for one opportunity

Data-minimization: profile fields are never echoed back verbatim in the match response;
only human-readable labels are returned.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.auth.deps import current_user_id
from app.schemas.profile import MatchReason, MatchResponse, ProfileResponse, ProfileUpdate

logger = logging.getLogger("verifai.profile")
router = APIRouter(prefix="/api/v1/profile", tags=["profile"])
OppId = Annotated[str, Path(min_length=1, max_length=64)]

_INTEREST_MAX_LEN = 100  # chars per interest string


def _sanitize_interests(interests: list[str]) -> list[str]:
    """Trim, lowercase, deduplicate, and cap each interest string."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in interests:
        cleaned = raw.strip()[:_INTEREST_MAX_LEN]
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result[:10]


def _profile_from_db(data: dict | None) -> ProfileResponse:
    if not data:
        return ProfileResponse()
    return ProfileResponse(
        education=data.get("education"),
        location=data.get("location"),
        experience_years=data.get("experience_years"),
        interests=data.get("interests", []),
    )


@router.get("", response_model=ProfileResponse)
def get_profile(request: Request, user_id: str = Depends(current_user_id)) -> ProfileResponse:
    """Return the authenticated user's profile. All fields default to null/empty."""
    data = request.app.state.store.get_profile(user_id)
    return _profile_from_db(data)


@router.patch("", response_model=ProfileResponse)
def update_profile(body: ProfileUpdate, request: Request,
                   user_id: str = Depends(current_user_id)) -> ProfileResponse:
    """Partial update. Only provided fields are changed; others are preserved."""
    store = request.app.state.store
    existing = store.get_profile(user_id) or {}
    # Apply each provided field
    update = body.model_dump(exclude_unset=True)
    if "interests" in update:
        update["interests"] = _sanitize_interests(update["interests"])
    merged = {**existing, **update}
    store.set_profile(user_id, merged)
    return _profile_from_db(merged)


def _match_reasons(profile: dict, opp_location: str | None,
                   opp_id: str, report_claims) -> list[MatchReason]:
    """
    Produce explainable match/mismatch reasons without echoing raw profile data.
    Each reason uses generic labels — no profile value is included verbatim.
    """
    reasons: list[MatchReason] = []

    # Location match
    p_loc = (profile.get("location") or "").strip().lower()
    o_loc = (opp_location or "").strip().lower()
    if p_loc and o_loc:
        if any(token in o_loc for token in p_loc.split()):
            reasons.append(MatchReason(
                reason="Location match",
                detail="Your preferred location overlaps with the opportunity's location.",
                positive=True))
        else:
            reasons.append(MatchReason(
                reason="Location mismatch",
                detail="Your preferred location differs from the opportunity's location.",
                positive=False))

    # Interest / keyword match against opportunity title + claims
    interests = [i.lower() for i in profile.get("interests", [])]
    if interests and report_claims:
        claim_text = " ".join(
            (c.get("normalized_value") or c.get("extracted_value", "")).lower()
            for c in report_claims
        )
        matched = [i for i in interests if i in claim_text]
        if matched:
            reasons.append(MatchReason(
                reason="Interest alignment",
                detail=f"The opportunity aligns with {len(matched)} of your stated interest(s).",
                positive=True))
        else:
            reasons.append(MatchReason(
                reason="No interest alignment",
                detail="None of your interests were found in the verified opportunity details.",
                positive=False))

    # Experience match (simplified: just note the level)
    exp = profile.get("experience_years")
    if exp is not None:
        if exp == 0:
            reasons.append(MatchReason(
                reason="Entry-level match",
                detail="You indicated no prior work experience, which fits typical internship requirements.",
                positive=True))
        elif exp <= 3:
            reasons.append(MatchReason(
                reason="Early-career profile",
                detail="Your experience level suits most internship and fellowship opportunities.",
                positive=True))
        else:
            reasons.append(MatchReason(
                reason="Experienced profile",
                detail="Your experience level may exceed typical internship requirements.",
                positive=False))

    return reasons


def _overall(reasons: list[MatchReason]) -> str:
    if not reasons:
        return "unknown"
    positive = sum(1 for r in reasons if r.positive)
    negative = sum(1 for r in reasons if not r.positive)
    if positive > 0 and negative == 0:
        return "good_match"
    if positive > 0:
        return "partial_match"
    return "no_match"


@router.get("/match/{opportunity_id}", response_model=MatchResponse)
def match_opportunity(opportunity_id: OppId, request: Request,
                      user_id: str = Depends(current_user_id)) -> MatchResponse:
    """
    Return explainable match reasons for one opportunity.
    Requires a valid session. Raw profile values are never exposed in the response.
    """
    store = request.app.state.store
    opp = store.get_opportunity(opportunity_id)
    if opp is None:
        raise HTTPException(404, "Opportunity not found.")
    profile = store.get_profile(user_id) or {}
    report = store.get_latest_report(opportunity_id)
    report_claims = []
    if report:
        # Serialize to plain dicts for the matching helper (no circular imports)
        for c in report.claims:
            report_claims.append({
                "extracted_value": c.normalized_value or "",
                "normalized_value": c.normalized_value,
            })
    reasons = _match_reasons(profile, opp.location, opportunity_id, report_claims)
    return MatchResponse(opportunity_id=opportunity_id, reasons=reasons, overall=_overall(reasons))
