import asyncio
import datetime as dt

import pytest

from app.discovery.base import RawSourceRecord
from app.discovery.errors import (ProviderAuthError, ProviderRateLimited, ProviderTimeout,
                                  ProviderUnavailable)
from app.discovery.mock import MockDiscoveryProvider
from app.discovery.retry import RetryPolicy, discover_with_policy
from app.schemas.discovery import DiscoverySearchRequest

REQ = DiscoverySearchRequest(query="test")
REC = RawSourceRecord(url="https://example.com/a", retrieved_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))


def run(provider, policy=RetryPolicy(), sleeps=None):
    async def fake_sleep(s):
        if sleeps is not None:
            sleeps.append(s)
    return asyncio.run(discover_with_policy(provider, REQ, policy, sleep=fake_sleep))


def test_success_first_try():
    p = MockDiscoveryProvider([REC])
    assert len(run(p).records) == 1 and p.calls == 1


def test_transient_errors_retry_with_exponential_backoff():
    p = MockDiscoveryProvider([REC], errors=[ProviderUnavailable(), ProviderTimeout()])
    sleeps = []
    assert run(p, RetryPolicy(max_attempts=3, base_delay_s=1), sleeps).records
    assert p.calls == 3 and sleeps == [1, 2]


def test_attempts_are_bounded():
    p = MockDiscoveryProvider(errors=[ProviderUnavailable()] * 5)
    with pytest.raises(ProviderUnavailable):
        run(p, RetryPolicy(max_attempts=3))
    assert p.calls == 3


def test_permanent_errors_are_not_retried():
    p = MockDiscoveryProvider(errors=[ProviderAuthError()])
    with pytest.raises(ProviderAuthError):
        run(p)
    assert p.calls == 1


def test_retry_after_is_honored_but_capped():
    p = MockDiscoveryProvider([REC], errors=[ProviderRateLimited(retry_after_s=100)])
    sleeps = []
    run(p, RetryPolicy(base_delay_s=0.5, max_delay_s=8), sleeps)
    assert sleeps == [8]


def test_slow_provider_times_out():
    p = MockDiscoveryProvider([REC], delay_s=0.2)
    with pytest.raises(ProviderTimeout):
        run(p, RetryPolicy(max_attempts=1, timeout_s=0.01))


def test_partial_flag_and_warnings_pass_through():
    r = run(MockDiscoveryProvider([REC], warnings=["w"], complete=False))
    assert r.complete is False and r.warnings == ["w"]


def test_invalid_policy_rejected():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)