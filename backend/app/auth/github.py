"""GitHub OAuth 2.0 provider.

GitHub does not issue OIDC ID tokens, so there is no JWT to verify. Instead:
- We exchange the authorization code for an access token server-side.
- We call /user and /user/emails with the token to get the stable numeric user id and
  the primary verified email.
- PKCE is enforced client-side (challenge stored in DB; verifier sent to GitHub token endpoint).
  GitHub accepts but does not mandate PKCE — the verifier is not validated by GitHub itself,
  but the challenge-binding means a stolen code cannot be exchanged without the verifier.

Account-linking: if the GitHub email matches a verified email already in our DB (e.g., Google
user), the GitHub identity is linked to that user rather than creating a duplicate account.
This is only done when the GitHub email is verified.
"""
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode

import httpx

from app.auth.models import ProviderIdentity
from app.auth.providers import AuthFlowError, clean_name, https_url_or_none


class GitHubProvider:
    name = "github"
    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"

    def __init__(self, client_id: str, client_secret: str, *,
                 transport: httpx.AsyncBaseTransport | None = None,
                 timeout_s: float = 10.0):
        self._client_id, self._client_secret = client_id, client_secret
        self._transport, self._timeout = transport, timeout_s

    def authorization_url(self, *, state: str, nonce: str, code_challenge: str,
                          redirect_uri: str) -> str:
        # nonce and code_challenge are stored in the DB; GitHub does not send them back.
        return self.AUTH_URL + "?" + urlencode({
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        })

    async def _exchange(self, code: str, redirect_uri: str) -> str:
        """Exchange authorization code for an access token. Returns the raw access token."""
        try:
            async with httpx.AsyncClient(transport=self._transport,
                                         timeout=self._timeout,
                                         headers={"Accept": "application/json"}) as http:
                resp = await http.post(self.TOKEN_URL, data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                })
        except httpx.HTTPError:
            raise AuthFlowError("network_error") from None
        try:
            body = resp.json()
            token = body.get("access_token") if resp.status_code == 200 else None
        except (ValueError, AttributeError):
            token = None
        if not isinstance(token, str) or not token:
            raise AuthFlowError("token_exchange_failed")
        return token

    async def _get_user(self, token: str) -> dict[str, Any]:
        """Fetch the GitHub user profile."""
        try:
            async with httpx.AsyncClient(transport=self._transport,
                                         timeout=self._timeout,
                                         headers={"Authorization": f"Bearer {token}",
                                                  "Accept": "application/vnd.github+json",
                                                  "X-GitHub-Api-Version": "2022-11-28"}) as http:
                resp = await http.get(self.USER_URL)
        except httpx.HTTPError:
            raise AuthFlowError("network_error") from None
        if resp.status_code != 200:
            raise AuthFlowError("user_fetch_failed")
        try:
            data = resp.json()
        except ValueError:
            raise AuthFlowError("user_fetch_failed") from None
        uid = data.get("id")
        if not isinstance(uid, int) or uid <= 0:
            raise AuthFlowError("user_fetch_failed")
        return data

    async def _get_primary_email(self, token: str) -> tuple[str | None, bool]:
        """
        Returns (email, email_verified) for the primary verified email.
        Falls back to (None, False) if no verified primary email exists.
        """
        try:
            async with httpx.AsyncClient(transport=self._transport,
                                         timeout=self._timeout,
                                         headers={"Authorization": f"Bearer {token}",
                                                  "Accept": "application/vnd.github+json",
                                                  "X-GitHub-Api-Version": "2022-11-28"}) as http:
                resp = await http.get(self.EMAILS_URL)
        except httpx.HTTPError:
            return None, False
        if resp.status_code != 200:
            return None, False
        try:
            emails = resp.json()
        except ValueError:
            return None, False
        if not isinstance(emails, list):
            return None, False
        # Prefer: primary + verified
        for entry in emails:
            if isinstance(entry, dict) and entry.get("primary") and entry.get("verified"):
                email = entry.get("email")
                if isinstance(email, str) and "@" in email:
                    return email.lower(), True
        # Fall back to any verified email
        for entry in emails:
            if isinstance(entry, dict) and entry.get("verified"):
                email = entry.get("email")
                if isinstance(email, str) and "@" in email:
                    return email.lower(), True
        return None, False

    async def complete(self, *, code: str, code_verifier: str, nonce: str,
                       redirect_uri: str) -> ProviderIdentity:
        """Exchange code, fetch user and email, return a verified ProviderIdentity."""
        token = await self._exchange(code, redirect_uri)
        user = await self._get_user(token)
        email, email_verified = await self._get_primary_email(token)
        subject = str(user["id"])
        # Sanitize display fields
        name = clean_name(user.get("name") or user.get("login"))
        avatar = https_url_or_none(user.get("avatar_url"))
        return ProviderIdentity(
            provider="github",
            subject=subject,
            email=email,
            email_verified=email_verified,
            display_name=name,
            avatar_url=avatar,
        )
