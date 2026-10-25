"""Provider error model. `transient` decides whether a retry is allowed."""


class ProviderError(Exception):
    transient = False
    code = "PROVIDER_ERROR"


class ProviderTimeout(ProviderError):
    transient = True
    code = "PROVIDER_TIMEOUT"


class ProviderRateLimited(ProviderError):
    transient = True
    code = "PROVIDER_RATE_LIMITED"

    def __init__(self, message: str = "rate limited", retry_after_s: float | None = None):
        super().__init__(message)
        self.retry_after_s = retry_after_s


class ProviderUnavailable(ProviderError):
    transient = True
    code = "PROVIDER_UNAVAILABLE"


class ProviderAuthError(ProviderError):
    code = "PROVIDER_AUTH_ERROR"


class ProviderBadResponse(ProviderError):
    code = "PROVIDER_BAD_RESPONSE"


class ProviderNotConfigured(ProviderError):
    """Missing SDK or credentials. Permanent: retrying cannot fix it."""

    code = "PROVIDER_NOT_CONFIGURED"
