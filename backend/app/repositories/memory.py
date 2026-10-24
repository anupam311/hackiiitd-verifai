"""Non-persistent store for tests and local runs. Replaced by SQLite in B10. Contains no seed data."""
from app.report.models import VerificationReport
from app.schemas.opportunity import Opportunity


class InMemoryStore:
    def __init__(self) -> None:
        self._opps: dict[str, Opportunity] = {}
        self._reports: dict[str, list[VerificationReport]] = {}

    def save_opportunity(self, opportunity: Opportunity) -> None:
        self._opps[opportunity.id] = opportunity

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        return self._opps.get(opportunity_id)

    def save_report(self, report: VerificationReport) -> None:
        self._reports.setdefault(report.opportunity_id, []).append(report)

    def get_latest_report(self, opportunity_id: str) -> VerificationReport | None:
        reports = self._reports.get(opportunity_id)
        return max(reports, key=lambda r: r.generated_at) if reports else None