"""OAuth/OIDC providers. Secrets and tokens stay on the server and are never logged or returned."""
import asyncio
import base64
import hashlib
import hmac
import re
from typing import Any, Awaitable, Callable, Protocol
from urllib.parse import urlencode

import httpx
import jwt

from app.auth.models import ProviderIdentity


class AuthFlowError(Exception):
    """Sign-in failed. `code` is safe to log; details (tokens, responses) are never attached."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OAuthProvider(Protocol):
    name: str

    def authorization_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str: ...

    async def complete(self, *, code: str, code_verifier: str, nonce: str,
                       redirect_uri: str) -> ProviderIdentity: ...


def pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def clean_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _CTRL.sub("", value).strip()[:100] or None


def https_url_or_none(value: Any) -> str | None:
    return value[:500] if isinstance(value, str) and value.startswith("https://") else None


class GoogleProvider:
    name = "google"
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
    ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

    def __init__(self, client_id: str, client_secret: str, *,
                 transport: httpx.AsyncBaseTransport | None = None,
                 key_resolver: Callable[[str], Awaitable[Any]] | None = None, timeout_s: float = 10.0):
        self._client_id, self._client_secret = client_id, client_secret
        self._transport, self._timeout = transport, timeout_s
        self._resolve = key_resolver or self._default_resolver()

    @staticmethod
    def _default_resolver() -> Callable[[str], Awaitable[Any]]:
        jwks = jwt.PyJWKClient(GoogleProvider.JWKS_URL, cache_keys=True)

        async def resolve(token: str) -> Any:
            return (await asyncio.to_thread(jwks.get_signing_key_from_jwt, token)).key

        return resolve

    def authorization_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str:
        return self.AUTH_URL + "?" + urlencode({
            "client_id": self._client_id, "redirect_uri": redirect_uri, "response_type": "code",
            "scope": "openid email profile", "state": state, "nonce": nonce,
            "code_challenge": code_challenge, "code_challenge_method": "S256"})

    async def _exchange(self, code: str, verifier: str, redirect_uri: str) -> str:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as http:
                resp = await http.post(self.TOKEN_URL, data={
                    "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                    "client_id": self._client_id, "client_secret": self._client_secret,
                    "code_verifier": verifier})
        except httpx.HTTPError:
            raise AuthFlowError("network_error") from None
        try:
            token = resp.json().get("id_token") if resp.status_code == 200 else None
        except ValueError:
            token = None
        if not isinstance(token, str) or not token:
            raise AuthFlowError("token_exchange_failed")
        return token

    async def _verify(self, token: str, nonce: str) -> dict[str, Any]:
        try:
            key = await self._resolve(token)
            claims = jwt.decode(token, key=key, algorithms=["RS256"], audience=self._client_id, leeway=30,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"]})
        except jwt.PyJWTError:
            raise AuthFlowError("invalid_id_token") from None
        sub = claims.get("sub")
        if (claims.get("iss") not in self.ISSUERS or not isinstance(sub, str) or not sub
                or not hmac.compare_digest(str(claims.get("nonce", "")).encode(), nonce.encode())):
            raise AuthFlowError("invalid_id_token")
        return claims

    async def complete(self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> ProviderIdentity:
        claims = await self._verify(await self._exchange(code, code_verifier, redirect_uri), nonce)
        email = claims.get("email") if isinstance(claims.get("email"), str) else None
        return ProviderIdentity(
            provider="google", subject=claims["sub"], email=email,
            email_verified=bool(email) and claims.get("email_verified") in (True, "true"),
            display_name=clean_name(claims.get("name")), avatar_url=https_url_or_none(claims.get("picture")))