"""TinyFish discovery adapter (ported from the radar.py workshop script).

radar.py stages and where they live here:
  stage 1/2  one agent per careers page, many in parallel -> `_run_pages` (+ optional seed pages)
  stage 3    Search finds the pages, agents work them     -> `TinyFishProvider.discover`

Contract with the rest of the backend (see docs/architecture.md):
- `discover` searches for pages, runs one TinyFish agent per page with a fixed output schema, and
  returns ONE `RawSourceRecord` per listing the agent reports. The record's URL is the listing's own
  apply link; `content_text` is a plain-text rendering of what the agent reported, which the normal
  pipeline then feeds to the LLM extractor and the deterministic verifier.
- `fetch` (used by rechecks) re-runs an agent on each known URL.
- Agent output is UNTRUSTED. It is rendered to plain text (markup and control characters stripped,
  lengths capped) and goes through the same extraction/grounding/verification as any other source.
  This adapter never assigns a source type (`official` is never inferred) and never invents values.
- A page the agent could not read is a warning (discover) or an observation with no content and
  outcome `unknown`/`timeout` (fetch). It is never evidence that an opportunity is closed.
- Errors are mapped to the `Provider*` model so `discover_with_policy` can retry only transient ones.
  Exception messages are never copied (they can echo URLs or credentials).
- `retrieved_at` is taken when the agent run returns, not later.

The SDK is imported lazily so the backend still starts (with discovery reported as not configured)
when the `tinyfish` package is not installed.
"""
import asyncio
import datetime as dt
import hashlib
import inspect
import json
import logging
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from app.discovery.base import DiscoveryResult, RawSourceRecord
from app.discovery.errors import (ProviderAuthError, ProviderBadResponse, ProviderError,
                                  ProviderNotConfigured, ProviderRateLimited, ProviderTimeout,
                                  ProviderUnavailable)
from app.discovery.normalize import canonicalize_url
from app.schemas.discovery import DiscoverySearchRequest
from app.schemas.enums import RetrievalOutcome

logger = logging.getLogger("verifai.discovery.tinyfish")

# Same idea as radar.py's SCHEMA: the same fields on every run. Nothing is "required" on purpose, so an
# agent can say "not stated" by leaving a field out rather than inventing a value.
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"opportunities": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "organization": {"type": "string"},
            "category": {"type": "string"},
            "location": {"type": "string"},
            "remote": {"type": "boolean"},
            "deadline": {"type": "string"},
            "status": {"type": "string"},
            "apply_link": {"type": "string"},
            "page_excerpt": {"type": "string"},
        }}}},
}

MAX_LISTINGS_PER_PAGE = 20
MAX_FIELD_CHARS = 300
MAX_EXCERPT_CHARS = 1500
SEARCH_TIMEOUT_S = 30.0

_LIST_KEYS = ("opportunities", "internships", "listings", "jobs", "results")
_TAGS = re.compile(r"<[^>]*>")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


# --------------------------------------------------------------------------------------- helpers
def _clean(value: Any, limit: int = MAX_FIELD_CHARS) -> str:
    """Untrusted scalar -> short single-line plain text ('' if unusable)."""
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return ""
    return " ".join(_CTRL.sub(" ", _TAGS.sub(" ", value)).split())[:limit]


def _http_url(value: Any) -> str | None:
    """Canonical http(s) URL or None. Credentials, fragments and tracking params are dropped."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return canonicalize_url(value)
    except ValueError:
        return None


def _is_completed(status: Any) -> bool:
    """Tolerant check for RunStatus.COMPLETED (enum member, its value, or a plain string)."""
    name = getattr(status, "name", None) or getattr(status, "value", None) or str(status)
    return str(name).rsplit(".", 1)[-1].strip().upper() == "COMPLETED"


def _status_code(exc: BaseException) -> int | None:
    for obj in (exc, getattr(exc, "response", None)):
        code = getattr(obj, "status_code", None)
        if isinstance(code, int) and not isinstance(code, bool):
            return code
    return None


def _retry_after(exc: BaseException) -> float | None:
    try:
        return float(exc.response.headers.get("retry-after"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return None


def classify_error(exc: BaseException) -> ProviderError:
    """Map any SDK/network exception to the provider error model. The message is dropped on purpose."""
    if isinstance(exc, ProviderError):
        return exc
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return ProviderTimeout("timeout")
    status = _status_code(exc)
    if status in (401, 403):
        return ProviderAuthError("credentials rejected")
    if status == 429:
        return ProviderRateLimited("rate limited", retry_after_s=_retry_after(exc))
    if status is not None and status >= 500:
        return ProviderUnavailable("server error")
    if isinstance(exc, (httpx.TransportError, ConnectionError)):
        return ProviderUnavailable("connection")
    return ProviderBadResponse("request rejected" if status is not None else "unexpected provider error")


def extract_listings(result: Any) -> list[dict[str, Any]] | None:
    """Pull listing dicts out of an agent result. None means the result is unusable (not 'no listings')."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return None
    if isinstance(result, list):
        return [i for i in result if isinstance(i, dict)]
    if not isinstance(result, dict):
        return None
    for key in _LIST_KEYS:
        if isinstance(result.get(key), list):
            return [i for i in result[key] if isinstance(i, dict)]
    lists = [v for v in result.values() if isinstance(v, list)]
    if len(lists) == 1:
        return [i for i in lists[0] if isinstance(i, dict)]
    if "title" in result:  # a single posting returned as a bare object (recheck)
        return [result]
    return None


def render_listing(item: dict[str, Any], page_url: str) -> str:
    """Plain-text rendering of one reported listing. This is the text the LLM extractor will read."""
    lines: list[str] = []
    for label, key in (("Title", "title"), ("Organization", "organization"), ("Category", "category"),
                       ("Location", "location")):
        if value := _clean(item.get(key)):
            lines.append(f"{label}: {value}")
    if isinstance(item.get("remote"), bool):
        lines.append(f"Remote: {'yes' if item['remote'] else 'no'}")
    for label, key in (("Deadline", "deadline"), ("Application status", "status"),
                       ("Apply link", "apply_link")):
        if value := _clean(item.get(key)):
            lines.append(f"{label}: {value}")
    if excerpt := _clean(item.get("page_excerpt"), MAX_EXCERPT_CHARS):
        lines.append(f"Listing text: {excerpt}")
    lines.append(f"Found on: {page_url}")
    return "\n".join(lines)


def build_goal(request: DiscoverySearchRequest) -> str:
    """The agent's instructions, built from the search request (radar.py's GOAL, generalized)."""
    kinds = ", ".join(c.value for c in request.categories) or "opportunities"
    parts = [f"Find {kinds} on this page that match: {request.query}."]
    if request.location:
        parts.append(f"Location of interest: {request.location}.")
    if request.fields_of_study:
        parts.append("Relevant fields: " + ", ".join(request.fields_of_study) + ".")
    if request.deadline_before:
        parts.append(f"If a deadline is shown, prefer listings due on or before {request.deadline_before.isoformat()}.")
    parts.append(
        f"Return at most {MAX_LISTINGS_PER_PAGE} listings. For each one return title, organization, "
        "category, location, remote (true/false), deadline, status (for example open, closed or rolling), "
        "apply_link (the direct URL to that posting — if no separate link exists, use the current page URL), "
        "and page_excerpt (the listing's own wording copied exactly as shown, under 600 characters). "
        "Report only what the page states; leave a field out when the page does not state it. "
        "Never guess dates. Always include apply_link even if it is the same as the current page URL.")
    return " ".join(parts)


RECHECK_GOAL = (
    "This page should describe one specific posting. Return that posting as a single item with title, "
    "organization, category, location, remote (true/false), deadline, status (for example open, closed or "
    "rolling), apply_link and page_excerpt (the posting's own wording copied exactly as shown, under 600 "
    "characters). Report only what the page states; leave a field out when the page does not state it. "
    "If the page no longer shows the posting, return an empty list.")


@dataclass
class _Page:
    """Outcome of one agent run: exactly one of run/error is set."""

    url: str
    run: Any = None
    error: ProviderError | None = None
    finished_at: dt.datetime | None = None


# -------------------------------------------------------------------------------------- provider
class TinyFishProvider:
    name = "tinyfish"

    def __init__(self, api_key: str | None = None, *, client: Any = None, max_pages: int = 5,
                 max_concurrency: int = 3, agent_timeout_s: float = 240.0, stealth: bool = False,
                 seed_pages: list[str] | None = None,
                 clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc)):
        if max_pages < 1 or max_concurrency < 1 or agent_timeout_s <= 0:
            raise ValueError("invalid TinyFish provider settings")
        self._api_key, self._client = api_key, client  # `client` lets tests inject a fake
        self._max_pages, self._max_concurrency = max_pages, max_concurrency
        self._agent_timeout_s, self._stealth, self._clock = agent_timeout_s, stealth, clock
        self._seeds = [u for u in (_http_url(s) for s in (seed_pages or [])) if u]

    @property
    def call_timeout_s(self) -> float:
        """Upper bound for one discover()/fetch() call: agent waves plus search/overhead.
        Use it as RetryPolicy.timeout_s; the default 30 s would cut every agent run short."""
        waves = math.ceil(self._max_pages / self._max_concurrency)
        return waves * self._agent_timeout_s + SEARCH_TIMEOUT_S + 15.0

    # ---- client
    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from tinyfish import AsyncTinyFish
            except ImportError:
                raise ProviderNotConfigured("the tinyfish package is not installed") from None
            try:
                if self._api_key:
                    try:
                        self._client = AsyncTinyFish(api_key=self._api_key)
                    except TypeError:
                        # Older/mock SDK that takes no keyword args: set env var and retry.
                        os.environ["TINYFISH_API_KEY"] = self._api_key
                        self._client = AsyncTinyFish()
                else:
                    self._client = AsyncTinyFish()  # reads TINYFISH_API_KEY automatically
            except Exception:  # noqa: BLE001 - e.g. no key anywhere; details may echo secrets
                raise ProviderNotConfigured("TinyFish client could not be created — check TINYFISH_API_KEY") from None
        return self._client

    async def aclose(self) -> None:
        """Best-effort cleanup at shutdown. The SDK's close method name is not assumed."""
        client, self._client = self._client, None
        for attr in ("aclose", "close"):
            fn = getattr(client, attr, None)
            if callable(fn):
                try:
                    res = fn()
                    if inspect.isawaitable(res):
                        await res
                except Exception:  # noqa: BLE001
                    logger.warning("tinyfish client close failed")
                return

    # ---- search (radar.py stage 3)
    async def _search_urls(self, request: DiscoverySearchRequest, want: int) -> list[str]:
        terms = [request.query, request.location or ""]
        terms += [c.value for c in request.categories if c.value not in request.query.lower()]
        query = " ".join(t for t in terms if t).strip()
        client = self._get_client()
        try:
            hits = client.search.query(query=query)
            if inspect.isawaitable(hits):
                hits = await asyncio.wait_for(hits, timeout=SEARCH_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001
            raise classify_error(exc) from None
        urls: list[str] = []
        for r in list(getattr(hits, "results", None) or []):
            raw = r.get("url") if isinstance(r, dict) else getattr(r, "url", None)
            url = _http_url(raw)
            if url and url not in urls:
                urls.append(url)
            if len(urls) >= want:
                break
        return urls

    # ---- agents (radar.py stages 1-2)
    async def _run_agent(self, url: str, goal: str) -> Any:
        kwargs: dict[str, Any] = {"url": url, "goal": goal, "output_schema": OUTPUT_SCHEMA}
        if self._stealth:  # radar.py: for sites that block bots
            from tinyfish import BrowserProfile
            kwargs["browser_profile"] = BrowserProfile.STEALTH
        return await asyncio.wait_for(self._get_client().agent.run(**kwargs), timeout=self._agent_timeout_s)

    async def _run_pages(self, urls: list[str], goal: str) -> list[_Page]:
        sem = asyncio.Semaphore(self._max_concurrency)

        async def one(url: str) -> _Page:
            async with sem:
                try:
                    run = await self._run_agent(url, goal)
                    return _Page(url, run=run, finished_at=self._clock())
                except Exception as exc:  # noqa: BLE001 - CancelledError is not an Exception: it propagates
                    err = classify_error(exc)
                    logger.warning("tinyfish agent failed code=%s", err.code)  # never the URL or message
                    return _Page(url, error=err, finished_at=self._clock())

        return list(await asyncio.gather(*(one(u) for u in urls)))

    @staticmethod
    def _escalate(pages: list[_Page]) -> None:
        """Credential/configuration problems affect every page, so they fail the whole call. If every
        page failed, raise (a transient error if there is one, so the retry layer can retry it).
        Otherwise the caller degrades to partial results."""
        errors = [p.error for p in pages if p.error is not None]
        for err in errors:
            if isinstance(err, (ProviderAuthError, ProviderNotConfigured)):
                raise err
        if pages and len(errors) == len(pages):
            raise next((e for e in errors if e.transient), errors[0])

    # ---- DiscoveryProvider
    async def discover(self, request: DiscoverySearchRequest) -> DiscoveryResult:
        urls = list(self._seeds[: self._max_pages])
        warnings: list[str] = []
        for u in await self._search_urls(request, self._max_pages):
            if u not in urls and len(urls) < self._max_pages:
                urls.append(u)
        if not urls:
            return DiscoveryResult(records=[], warnings=["TinyFish search returned no pages."], complete=True)

        pages = await self._run_pages(urls, build_goal(request))
        self._escalate(pages)

        records: list[RawSourceRecord] = []
        complete = True
        skipped_no_title = 0
        for page in pages:
            domain = _domain(page.url)
            if page.error is not None or not _is_completed(getattr(page.run, "status", None)):
                complete = False
                why = page.error.code if page.error else "agent did not complete"
                warnings.append(f"{domain}: the page could not be read ({why}); "
                                "this does not show any opportunity there is closed.")
                continue
            items = extract_listings(getattr(page.run, "result", None))
            if items is None:
                complete = False
                warnings.append(f"{domain}: the agent returned no usable result.")
                continue
            seen_links: set[str] = set()
            for item in items[:MAX_LISTINGS_PER_PAGE]:
                title = _clean(item.get("title"))
                if not title:
                    skipped_no_title += 1
                    continue
                # Use the dedicated apply_link when available; fall back to the page URL.
                # Listings that share the same URL (e.g. all on one careers page) get a
                # synthetic query param so they each produce a distinct, canonicalisable URL.
                # (Fragments are stripped by canonicalize_url, so we use ?__id= instead.)
                link = _http_url(item.get("apply_link")) or page.url
                if link in seen_links:
                    # Two listings share the same apply_link on this page — disambiguate.
                    t_hash = hashlib.sha256((page.url + title).encode()).hexdigest()[:10]
                    link = f"{page.url}?__id={t_hash}"
                seen_links.add(link)
                records.append(RawSourceRecord(
                    url=link, title=title or None, retrieved_at=page.finished_at,
                    http_status=None, retrieval_outcome=RetrievalOutcome.ok, source_type_hint=None,
                    content_text=render_listing(item, page.url)))
        if skipped_no_title:
            warnings.append(f"{skipped_no_title} listing(s) were skipped because they had no title.")
        if len(records) > request.limit:
            records = records[: request.limit]
            warnings.append(f"Results were limited to {request.limit} listings.")
        return DiscoveryResult(records=records, warnings=warnings, complete=complete)

    async def fetch(self, urls: list[str]) -> DiscoveryResult:
        """Recheck: one agent per known URL. Every requested URL gets a record (with the time it was
        looked at), so a failure shows up as an unavailable source rather than silently vanishing."""
        wanted: list[str] = []
        for u in urls:
            c = _http_url(u)
            if c and c not in wanted:
                wanted.append(c)
        if not wanted:
            return DiscoveryResult(records=[], warnings=[], complete=True)
        pages = await self._run_pages(wanted, RECHECK_GOAL)
        self._escalate(pages)

        records: list[RawSourceRecord] = []
        warnings: list[str] = []
        complete = True
        for page in pages:
            base = dict(url=page.url, retrieved_at=page.finished_at, http_status=None, source_type_hint=None)
            if page.error is not None or not _is_completed(getattr(page.run, "status", None)):
                complete = False
                timed_out = isinstance(page.error, ProviderTimeout)
                records.append(RawSourceRecord(
                    **base, retrieval_outcome=RetrievalOutcome.timeout if timed_out else RetrievalOutcome.unknown))
                warnings.append(f"{_domain(page.url)}: the page could not be read.")
                continue
            items = extract_listings(getattr(page.run, "result", None))
            if items is None:
                complete = False
                records.append(RawSourceRecord(**base, retrieval_outcome=RetrievalOutcome.unknown))
                warnings.append(f"{_domain(page.url)}: the agent returned no usable result.")
                continue
            item = next((i for i in items if _http_url(i.get("apply_link")) == page.url), items[0] if items else None)
            text = render_listing(item, page.url) if item and _clean(item.get("title")) else None
            records.append(RawSourceRecord(
                **base, title=_clean(item.get("title"), 300) or None if item else None,
                retrieval_outcome=RetrievalOutcome.ok, content_text=text))
        return DiscoveryResult(records=records, warnings=warnings, complete=complete)


def _domain(url: str) -> str:
    return urlsplit(url).hostname or "unknown"


def tinyfish_sdk_installed() -> bool:
    import importlib.util
    return importlib.util.find_spec("tinyfish") is not None
