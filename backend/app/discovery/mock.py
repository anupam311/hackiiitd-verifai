"""Scriptable provider for tests. Contains no built-in data: callers supply every record."""
import asyncio

from app.discovery.base import DiscoveryResult, RawSourceRecord
from app.discovery.errors import ProviderError
from app.discovery.normalize import canonicalize_url
from app.schemas.discovery import DiscoverySearchRequest


class MockDiscoveryProvider:
    name = "mock"

    def __init__(
        self,
        records: list[RawSourceRecord] | None = None,
        *,
        errors: list[ProviderError] | None = None,  # raised one per call, then success
        warnings: list[str] | None = None,
        complete: bool = True,
        delay_s: float = 0.0,
    ):
        self._records = list(records or [])
        self._errors = list(errors or [])
        self._warnings = list(warnings or [])
        self._complete = complete
        self._delay_s = delay_s
        self.calls = 0
        self.fetch_calls = 0

    async def discover(self, request: DiscoverySearchRequest) -> DiscoveryResult:
        self.calls += 1
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        if self._errors:
            raise self._errors.pop(0)
        return DiscoveryResult(
            records=self._records[: request.limit], warnings=self._warnings, complete=self._complete
        )

    async def fetch(self, urls: list[str]) -> DiscoveryResult:
        self.fetch_calls += 1
        if self._errors:
            raise self._errors.pop(0)
        wanted = {canonicalize_url(u) for u in urls}
        keep = [r for r in self._records if canonicalize_url(r.url) in wanted]
        return DiscoveryResult(records=keep, warnings=self._warnings, complete=self._complete)