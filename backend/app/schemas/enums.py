"""Shared enumerations. Status values mirror docs/verification_policy.md."""
from enum import Enum


class OpportunityCategory(str, Enum):
    internship = "internship"
    scholarship = "scholarship"
    fellowship = "fellowship"
    job = "job"
    research = "research"
    competition = "competition"
    other = "other"


class OpportunityStatus(str, Enum):
    open = "open"
    closed = "closed"
    unknown = "unknown"


class SourceType(str, Enum):
    official = "official"
    employer = "employer"
    institution = "institution"
    aggregator = "aggregator"
    community = "community"
    other = "other"


class RetrievalOutcome(str, Enum):
    ok = "ok"
    not_found = "not_found"
    blocked = "blocked"
    http_error = "http_error"
    timeout = "timeout"
    unknown = "unknown"


class Freshness(str, Enum):
    fresh = "fresh"
    stale = "stale"
    unknown = "unknown"


class ClaimType(str, Enum):
    deadline = "deadline"
    application_status = "application_status"
    application_url = "application_url"
    eligibility = "eligibility"
    stipend = "stipend"
    location = "location"
    duration = "duration"
    start_date = "start_date"
    organization = "organization"
    other = "other"


class VerificationStatus(str, Enum):
    confirmed = "confirmed"
    partially_confirmed = "partially_confirmed"
    conflicting = "conflicting"
    unverified = "unverified"
    unavailable = "unavailable"


class RunState(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    partial = "partial"
    failed = "failed"