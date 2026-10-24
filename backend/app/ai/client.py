"""LLM client interface, bounded retry, and the OpenAI adapter."""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Protocol

from app.ai.errors import (LLMAuthError, LLMError, LLMNotConfigured, LLMOutputInvalid,
                           LLMRateLimited, LLMTimeout, LLMUnavailable)
from app.discovery.retry import RetryPolicy

logger = logging.getLogger("verifai.ai")


class LLMClient(Protocol):
    name: str
    model: str

    async def complete_json(self, *, system: str, user: str, schema: dict[str, Any],
                            schema_name: str) -> str: ...


async def complete_with_policy(
    llm: LLMClient, *, system: str, user: str, schema: dict[str, Any], schema_name: str,
    policy: RetryPolicy = RetryPolicy(max_attempts=3, timeout_s=60.0),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> str:
    """Timeout + exponential backoff for transient errors only; auth and output errors are not retried."""
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await asyncio.wait_for(
                llm.complete_json(system=system, user=user, schema=schema, schema_name=schema_name),
                timeout=policy.timeout_s)
        except asyncio.TimeoutError:
            err: LLMError = LLMTimeout("llm call timed out")
        except LLMError as exc:
            err = exc
        logger.warning("llm attempt=%d provider=%s code=%s", attempt, llm.name, err.code)  # no content
        if not err.transient or attempt == policy.max_attempts:
            raise err
        await sleep(policy.delay_for(attempt, getattr(err, "retry_after_s", None)))
    raise AssertionError("unreachable")


def map_openai_error(exc: Exception) -> LLMError:
    """Map SDK exceptions to our model. Messages are dropped on purpose (they can echo request data)."""
    import openai

    if isinstance(exc, openai.APITimeoutError):  # subclass of APIConnectionError: check first
        return LLMTimeout("timeout")
    if isinstance(exc, openai.RateLimitError):
        retry_after = None
        try:
            retry_after = float(exc.response.headers.get("retry-after"))
        except (AttributeError, TypeError, ValueError):
            pass
        return LLMRateLimited("rate limited", retry_after_s=retry_after)
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return LLMAuthError("auth")
    if isinstance(exc, openai.APIConnectionError):
        return LLMUnavailable("connection")
    if isinstance(exc, openai.APIStatusError):
        return LLMUnavailable("server error") if exc.status_code >= 500 else LLMError("request rejected")
    return LLMError("unexpected llm error")


class OpenAIClient:
    name = "openai"

    def __init__(self, api_key: str | None, model: str | None, *, client: Any = None,
                 timeout_s: float = 60.0):
        if not api_key or not model:
            raise LLMNotConfigured("OPENAI_API_KEY and OPENAI_MODEL must both be set")
        if client is None:
            from openai import AsyncOpenAI

            # max_retries=0: bounded retries are applied by complete_with_policy.
            client = AsyncOpenAI(api_key=api_key, timeout=timeout_s, max_retries=0)
        self._client = client
        self.model = model

    async def complete_json(self, *, system: str, user: str, schema: dict[str, Any],
                            schema_name: str) -> str:
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
            )
        except Exception as exc:  # noqa: BLE001
            raise map_openai_error(exc) from None
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None) or choice.finish_reason != "stop" \
                or not choice.message.content:
            raise LLMOutputInvalid("refused, truncated or empty output")
        return choice.message.content