"""Bounded timeout + exponential backoff, applied only to transient provider failures."""
import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.discovery.base import DiscoveryProvider, DiscoveryResult
from app.discovery.errors import ProviderError, ProviderTimeout
from app.schemas.discovery import DiscoverySearchRequest

logger = logging.getLogger("verifai.discovery")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0
    timeout_s: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.timeout_s <= 0 or self.base_delay_s < 0:
            raise ValueError("invalid retry policy")

    def delay_for(self, attempt: int, retry_after_s: float | None = None) -> float:
        delay = min(self.max_delay_s, self.base_delay_s * 2 ** (attempt - 1))
        if retry_after_s is not None:
            delay = min(self.max_delay_s, max(delay, retry_after_s))
        return delay


async def discover_with_policy(
    provider: DiscoveryProvider,
    request: DiscoverySearchRequest,
    policy: RetryPolicy = RetryPolicy(),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    on_retry: Callable[[int, str, float], None] | None = None,
) -> DiscoveryResult:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await asyncio.wait_for(provider.discover(request), timeout=policy.timeout_s)
        except asyncio.TimeoutError:
            err: ProviderError = ProviderTimeout("provider call timed out")
        except ProviderError as exc:
            err = exc
        # Log provider, attempt and error code only: never queries, tokens or page content.
        logger.warning("discovery attempt=%d provider=%s code=%s", attempt, provider.name, err.code)
        if not err.transient or attempt == policy.max_attempts:
            raise err
        delay = policy.delay_for(attempt, getattr(err, "retry_after_s", None))
        if on_retry:
            on_retry(attempt, err.code, delay)
        await sleep(delay)
    raise AssertionError("unreachable")