"""LLM error model. `transient` decides whether a bounded retry is allowed."""


class LLMError(Exception):
    transient = False
    code = "LLM_ERROR"


class LLMTimeout(LLMError):
    transient = True
    code = "LLM_TIMEOUT"


class LLMRateLimited(LLMError):
    transient = True
    code = "LLM_RATE_LIMITED"

    def __init__(self, message: str = "rate limited", retry_after_s: float | None = None):
        super().__init__(message)
        self.retry_after_s = retry_after_s


class LLMUnavailable(LLMError):
    transient = True
    code = "LLM_UNAVAILABLE"


class LLMAuthError(LLMError):
    code = "LLM_AUTH_ERROR"


class LLMNotConfigured(LLMError):
    code = "LLM_NOT_CONFIGURED"


class LLMOutputInvalid(LLMError):
    """Output was missing, refused, not JSON, or did not match the schema. Never retried."""

    code = "LLM_OUTPUT_INVALID"