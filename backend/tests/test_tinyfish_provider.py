"""TinyFish adapter tests. A fake SDK client stands in for the network: nothing here calls TinyFish."""
import asyncio
import json
import os
import sys
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import SESSION_COOKIE, hash_token
from app.auth.models import ProviderIdentity
from app.config import Settings
from app.discovery import tinyfish as tf
from app.discovery.errors import (ProviderAuthError, ProviderBadResponse, ProviderNotConfigured,
                                  ProviderRateLimited, ProviderTimeout, ProviderUnavailable)
from app.discovery.retry import RetryPolicy, discover_with_policy
from app.discovery.tinyfish import TinyFishProvider
from app.main import create_app
from app.repositories.sqlite import SqliteStore
from app.schemas.common import utc_now
from app.schemas.discovery import DiscoverySearchRequest
from app.schemas.enums import OpportunityCategory, OpportunityStatus, RetrievalOutcome

REQ = DiscoverySearchRequest(query="software internships", location="Bengaluru",
                             categories=[OpportunityCategory.internship])
PAGE_A, PAGE_B = "https://careers.example.com/jobs", "https://jobs.example.org/open"


# ------------------------------------------------------------------------------------------ fakes
class HttpError(Exception):
    def __init__(self, status, headers=None):
        super().__init__("secret-token-in-message")
        self.status_code = status
        self.response = SimpleNamespace(status_code=status, headers=headers or {})


def run(result, status="COMPLETED"):
    return SimpleNamespace(status=SimpleNamespace(name=status), result=result)


def listing(n, **kw):
    item = {"title": f"Software Intern {n}", "organization": "Example Org", "category": "internship",
            "location": "Bengaluru", "remote": True, "deadline": "June 15, 2026", "status": "open",
            "apply_link": f"https://careers.example.com/jobs/{n}?utm_source=x",
            "page_excerpt": f"Applications for intern {n} are open."}
    item.update(kw)
    return item


class FakeClient:
    """pages: url -> result object | Exception. Records every call so tests can assert on the goal/schema."""

    def __init__(self, pages=None, search_urls=(), search_error=None, async_search=False, delay_s=0.0):
        self.pages, self.agent_calls, self.search_calls = pages or {}, [], []
        self._urls, self._search_error, self._async, self._delay = search_urls, search_error, async_search, delay_s
        self.in_flight = self.max_in_flight = 0
        self.agent = SimpleNamespace(run=self._run)
        self.search = SimpleNamespace(query=self._query)

    def _query(self, query):
        self.search_calls.append(query)
        if self._search_error:
            raise self._search_error
        out = SimpleNamespace(results=[SimpleNamespace(url=u) for u in self._urls])
        if not self._async:
            return out

        async def later():
            return out
        return later()

    async def _run(self, **kw):
        self.agent_calls.append(kw)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
            outcome = self.pages.get(kw["url"], run({"opportunities": []}))
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        finally:
            self.in_flight -= 1


def provider(client, **kw):
    kw.setdefault("clock", utc_now)
    return TinyFishProvider("key", client=client, **kw)


def discover(p, req=REQ):
    return asyncio.run(p.discover(req))


# ----------------------------------------------------------------------------------------- discover
def test_discover_returns_one_record_per_listing_with_fetch_time_and_no_source_type():
    client = FakeClient({PAGE_A: run({"opportunities": [listing(1), listing(2)]}),
                         PAGE_B: run({"opportunities": [listing(3, apply_link="https://jobs.example.org/open/3")]})},
                        search_urls=[PAGE_A, PAGE_B])
    before = utc_now()
    res = discover(provider(client))
    assert res.complete and not res.warnings and len(res.records) == 3
    r = res.records[0]
    assert r.url == "https://careers.example.com/jobs/1"  # tracking parameter removed
    assert r.retrieved_at.tzinfo is not None and before <= r.retrieved_at <= utc_now()
    assert r.retrieval_outcome == RetrievalOutcome.ok and r.http_status is None
    assert r.source_type_hint is None  # authority is never assumed from a provider
    assert "Title: Software Intern 1" in r.content_text and "Found on: " + PAGE_A in r.content_text
    assert "Remote: yes" in r.content_text


def test_agent_gets_the_goal_schema_and_search_gets_the_query():
    client = FakeClient({PAGE_A: run({"opportunities": []})}, search_urls=[PAGE_A])
    discover(provider(client))
    assert client.search_calls == ["software internships Bengaluru"]  # 'internship' not repeated: already implied
    call = client.agent_calls[0]
    assert call["url"] == PAGE_A and call["output_schema"] is tf.OUTPUT_SCHEMA
    assert "software internships" in call["goal"] and "Bengaluru" in call["goal"] and "internship" in call["goal"]
    assert "Never guess" in call["goal"]


def test_async_search_clients_are_supported():
    client = FakeClient({PAGE_A: run({"opportunities": [listing(1)]})}, search_urls=[PAGE_A], async_search=True)
    assert len(discover(provider(client)).records) == 1


def test_seed_pages_come_first_are_deduplicated_and_page_count_is_capped():
    client = FakeClient(search_urls=[PAGE_B + "#frag", PAGE_A, "https://x.example.net/1", "ftp://bad", "not a url"])
    discover(provider(client, max_pages=3, seed_pages=[PAGE_A + "/"]))
    assert [c["url"] for c in client.agent_calls] == [PAGE_A, PAGE_B, "https://x.example.net/1"]


def test_agents_run_in_parallel_but_bounded():
    urls = [f"https://s{i}.example.com/jobs" for i in range(6)]
    client = FakeClient(search_urls=urls, delay_s=0.02)
    discover(provider(client, max_pages=6, max_concurrency=2))
    assert client.max_in_flight == 2


def test_no_search_results_is_an_empty_complete_result_with_a_warning():
    res = discover(provider(FakeClient(search_urls=[])))
    assert res.records == [] and res.complete and res.warnings


def test_limit_is_enforced():
    client = FakeClient({PAGE_A: run({"opportunities": [listing(i) for i in range(1, 6)]})}, search_urls=[PAGE_A])
    res = discover(provider(client), DiscoverySearchRequest(query="x", limit=2))
    assert len(res.records) == 2 and any("limited" in w for w in res.warnings)


def test_listings_without_their_own_link_are_skipped_and_reported():
    items = [listing(1), listing(2, apply_link=""), listing(3, apply_link=PAGE_A),
             listing(4, title=""), listing(5, apply_link="https://careers.example.com/jobs/dup"),
             listing(6, apply_link="https://careers.example.com/jobs/dup")]
    res = discover(provider(FakeClient({PAGE_A: run({"opportunities": items})}, search_urls=[PAGE_A])))
    assert [r.title for r in res.records] == ["Software Intern 1"]
    assert any("5 listing(s) were skipped" in w for w in res.warnings)


def test_agent_output_is_sanitized_and_capped():
    nasty = listing(1, title="<script>x</script>Intern\x00\x07 <b>role</b>", page_excerpt="a " * 5000,
                    location={"not": "a string"}, remote="yes")
    res = discover(provider(FakeClient({PAGE_A: run({"opportunities": [nasty]})}, search_urls=[PAGE_A])))
    text = res.records[0].content_text
    assert "<" not in text.split("Found on")[0] and "\x00" not in text and "\x07" not in text
    assert "Location:" not in text and "Remote:" not in text  # wrong types are dropped, not guessed
    assert len(text) < 2000


@pytest.mark.parametrize("result", [
    {"internships": [listing(1)]},          # radar.py's own key
    {"anything": [listing(1)]},             # single list under an unknown key
    json.dumps({"opportunities": [listing(1)]}),  # JSON string
    [listing(1)],                           # bare list
])
def test_result_shapes_are_tolerated(result):
    res = discover(provider(FakeClient({PAGE_A: run(result)}, search_urls=[PAGE_A])))
    assert len(res.records) == 1


def test_unusable_or_failed_pages_make_the_result_partial_not_closed():
    client = FakeClient({PAGE_A: run({"opportunities": [listing(1)]}),
                         PAGE_B: run(None),
                         "https://c.example.com/x": run({"opportunities": [listing(9)]}, status="FAILED")},
                        search_urls=[PAGE_A, PAGE_B, "https://c.example.com/x"])
    res = discover(provider(client))
    assert len(res.records) == 1 and res.complete is False
    assert all("does not show" in w or "no usable" in w for w in res.warnings) and len(res.warnings) == 2
    assert all("https://" not in w for w in res.warnings)  # domains only


def test_one_failing_page_degrades_to_partial_results():
    client = FakeClient({PAGE_A: run({"opportunities": [listing(1)]}), PAGE_B: HttpError(503)},
                        search_urls=[PAGE_A, PAGE_B])
    res = discover(provider(client))
    assert len(res.records) == 1 and res.complete is False and "PROVIDER_UNAVAILABLE" in res.warnings[0]


def test_every_page_failing_transiently_raises_so_the_retry_layer_can_retry():
    client = FakeClient({PAGE_A: HttpError(503), PAGE_B: HttpError(429, {"retry-after": "3"})},
                        search_urls=[PAGE_A, PAGE_B])
    with pytest.raises(ProviderUnavailable):
        discover(provider(client))


def test_credential_errors_fail_the_whole_call_even_if_other_pages_work():
    client = FakeClient({PAGE_A: run({"opportunities": [listing(1)]}), PAGE_B: HttpError(401)},
                        search_urls=[PAGE_A, PAGE_B])
    with pytest.raises(ProviderAuthError):
        discover(provider(client))


def test_search_errors_are_classified():
    with pytest.raises(ProviderRateLimited) as e:
        discover(provider(FakeClient(search_error=HttpError(429, {"retry-after": "7"}))))
    assert e.value.retry_after_s == 7.0
    with pytest.raises(ProviderBadResponse):
        discover(provider(FakeClient(search_error=ValueError("boom"))))


def test_slow_agent_times_out_per_page():
    p = provider(FakeClient(search_urls=[PAGE_A], delay_s=0.5), agent_timeout_s=0.02)
    with pytest.raises(ProviderTimeout):
        discover(p)


def test_error_messages_never_leak():
    for exc in (HttpError(500), HttpError(401), HttpError(400), RuntimeError("secret-token-in-message")):
        assert "secret" not in str(tf.classify_error(exc))


def test_retry_layer_uses_the_long_timeout_and_retries_transient_failures():
    p = provider(FakeClient(search_urls=[PAGE_A]), max_pages=5, max_concurrency=3, agent_timeout_s=240)
    assert p.call_timeout_s > 240 * 2  # two waves of agents; the default 30 s would cut runs short
    calls = {"n": 0}
    good = run({"opportunities": [listing(1)]})

    class Flaky(FakeClient):
        async def _run(self, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise HttpError(503)
            return good
    flaky = Flaky(search_urls=[PAGE_A])
    flaky.agent = SimpleNamespace(run=flaky._run)

    async def no_sleep(_):
        pass
    res = asyncio.run(discover_with_policy(provider(flaky), REQ, RetryPolicy(base_delay_s=0), sleep=no_sleep))
    assert len(res.records) == 1 and calls["n"] == 2


# -------------------------------------------------------------------------------------------- fetch
def test_fetch_returns_a_record_for_every_url_and_failures_are_not_closures():
    u1, u2, u3, u4 = (f"https://careers.example.com/jobs/{i}" for i in range(1, 5))
    client = FakeClient({u1: run({"opportunities": [listing(1)]}),
                         u2: HttpError(503), u3: run(None), u4: run({"opportunities": []})})
    res = asyncio.run(provider(client).fetch([u1, u2, u3, u4, u1]))
    by = {r.url: r for r in res.records}
    assert set(by) == {u1, u2, u3, u4} and len(res.records) == 4
    assert by[u1].content_text and by[u1].retrieval_outcome == RetrievalOutcome.ok
    assert by[u2].content_text is None and by[u2].retrieval_outcome == RetrievalOutcome.unknown
    assert by[u3].content_text is None and by[u4].content_text is None
    assert res.complete is False
    assert client.agent_calls[0]["goal"] == tf.RECHECK_GOAL


def test_fetch_where_every_url_times_out_raises_for_the_retry_layer():
    p = provider(FakeClient(delay_s=0.5), agent_timeout_s=0.02)
    with pytest.raises(ProviderTimeout):
        asyncio.run(p.fetch([PAGE_A]))


def test_fetch_with_nothing_to_fetch_is_a_no_op():
    client = FakeClient()
    res = asyncio.run(provider(client).fetch(["not a url"]))
    assert res.records == [] and client.agent_calls == []


def test_fetch_prefers_the_listing_matching_the_url():
    url = "https://careers.example.com/jobs/2"
    client = FakeClient({url: run({"opportunities": [listing(1), listing(2)]})})
    res = asyncio.run(provider(client).fetch([url]))
    assert "Software Intern 2" in res.records[0].content_text


# ----------------------------------------------------------------------------- client / configuration
def test_missing_sdk_is_reported_as_not_configured(monkeypatch):
    monkeypatch.setitem(sys.modules, "tinyfish", None)  # makes `import tinyfish` raise ImportError
    with pytest.raises(ProviderNotConfigured):
        discover(TinyFishProvider("key"))
    assert tf.tinyfish_sdk_installed() is False


def test_client_is_created_with_the_key_or_via_environment(monkeypatch):
    made = []

    class WithKey:
        def __init__(self, api_key=None):
            made.append(api_key)
            self.agent = self.search = SimpleNamespace(run=None, query=lambda **k: SimpleNamespace(results=[]))

    class NoKeyArg:
        def __init__(self):
            made.append("env")
            self.search = SimpleNamespace(query=lambda **k: SimpleNamespace(results=[]))

    monkeypatch.setitem(sys.modules, "tinyfish", SimpleNamespace(AsyncTinyFish=WithKey))
    discover(TinyFishProvider("k1"))
    monkeypatch.setitem(sys.modules, "tinyfish", SimpleNamespace(AsyncTinyFish=NoKeyArg))
    monkeypatch.setenv("TINYFISH_API_KEY", "placeholder")
    monkeypatch.delenv("TINYFISH_API_KEY")  # absent now; monkeypatch restores that state afterwards
    discover(TinyFishProvider("k2"))
    assert os.environ["TINYFISH_API_KEY"] == "k2"
    assert made == ["k1", "env"]


def test_invalid_settings_rejected():
    with pytest.raises(ValueError):
        TinyFishProvider("k", max_pages=0)


def test_aclose_is_best_effort():
    closed = []

    class C:
        async def aclose(self):
            closed.append(1)
    p = provider(C())
    asyncio.run(p.aclose())
    asyncio.run(p.aclose())  # second call: nothing left, no error
    assert closed == [1]


# ---------------------------------------------------------------------------------- app wiring + e2e
def settings(**env):
    return Settings(_env_file=None, **env)


def test_app_builds_a_tinyfish_provider_from_the_api_key(monkeypatch):
    monkeypatch.setattr("app.main.tinyfish_sdk_installed", lambda: True)
    app = create_app(settings(TINYFISH_API_KEY="k", tinyfish_max_pages=2, tinyfish_seed_pages="https://a.example.com/jobs, "))
    p = app.state.provider
    assert isinstance(p, TinyFishProvider) and app.state.retry_policy.timeout_s == p.call_timeout_s
    assert app.state.retry_policy.max_attempts == 2


def test_app_without_key_or_sdk_still_starts_and_reports_not_configured(monkeypatch):
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    assert create_app(settings()).state.provider is None
    monkeypatch.setattr("app.main.tinyfish_sdk_installed", lambda: False)
    app = create_app(settings(TINYFISH_API_KEY="k"))
    assert app.state.provider is None
    r = TestClient(app).post("/api/v1/discovery/search", json={"query": "x"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


class ListingLLM:
    """Pretends to be the extractor: quotes verbatim from the text the TinyFish adapter produced."""
    name, model = "fake", "m"

    async def complete_json(self, *, system, user, schema, schema_name):
        facts = [("organization", "Example Org", "Organization: Example Org"),
                 ("application_status", "open", "Application status: open"),
                 ("deadline", "June 15, 2026", "Deadline: June 15, 2026")]
        return json.dumps({"opportunity_title": "Software Intern 1", "opportunity_category": "internship",
                           "facts": [{"claim_type": t, "extracted_value": v, "excerpt": e, "confidence": 0.9}
                                     for t, v, e in facts]})


def test_end_to_end_discovery_and_recheck_through_the_api():
    client = FakeClient({PAGE_A: run({"opportunities": [listing(1)]}),
                         "https://careers.example.com/jobs/1": run({"opportunities": [listing(1)]})},
                        search_urls=[PAGE_A])
    fast = RetryPolicy(base_delay_s=0)
    app = create_app(settings(), provider=provider(client), llm=ListingLLM(), retry_policy=fast,
                     extract_retry_policy=fast)

    def wait(c, rid):
        for _ in range(100):
            body = c.get(f"/api/v1/runs/{rid}").json()
            if body["state"] in ("completed", "partial", "failed", "cancelled"):
                return body
            time.sleep(0.05)
        raise AssertionError("run did not finish")

    with TestClient(app) as c:
        rid = c.post("/api/v1/discovery/search", json={"query": "software internships"}).json()["run_id"]
        body = wait(c, rid)
        assert body["state"] == "completed", body
        opp = body["opportunities"][0]
        assert opp["title"] == "Software Intern 1" and opp["organization"] == "Example Org"
        # One unclassified source can never confirm an opportunity: no open/closed claim is made.
        assert opp["status"] == OpportunityStatus.unknown.value
        report = c.get(f"/api/v1/opportunities/{opp['id']}/report").json()
        assert {s["url"] for s in report["sources"]} == {"https://careers.example.com/jobs/1"}
        assert all(cl["status"] != "confirmed" for cl in report["claims"])

        # recheck needs a signed-in user
        assert c.post(f"/api/v1/opportunities/{opp['id']}/recheck").status_code == 401
        user = app.state.store.find_or_create_user(ident("google", "g1", "jane@example.com"), utc_now())
        token = "t" * 40
        app.state.store.create_session(hash_token(token), user.id, utc_now(), utc_now() + timedelta(days=1))
        c.cookies.set(SESSION_COOKIE, token)
        rc = c.post(f"/api/v1/opportunities/{opp['id']}/recheck")
        assert rc.status_code == 202
        done = wait(c, rc.json()["run_id"])
        assert done["state"] == "completed" and done["kind"] == "recheck", done
        assert [a["url"] for a in client.agent_calls[1:]] == ["https://careers.example.com/jobs/1"]
        history = c.get(f"/api/v1/opportunities/{opp['id']}/history").json()
        assert len(history["runs"]) == 2 and history["runs"][0]["changes_since_previous"] is not None


# ------------------------------------------------------------ SQLite account linking (production store)
def ident(provider_, subject, email, verified=True):
    return ProviderIdentity(provider=provider_, subject=subject, email=email, email_verified=verified,
                            display_name="Jane")


def test_sqlite_links_github_to_google_user_by_verified_email():
    s = SqliteStore(":memory:")
    google = s.find_or_create_user(ident("google", "g1", "Jane@Example.com"), utc_now())
    gh = s.find_or_create_user(ident("github", "42", "jane@example.com"), utc_now())
    assert gh.id == google.id and gh.providers == ["github", "google"]
    assert s.find_or_create_user(ident("github", "42", None, False), utc_now()).id == google.id  # by identity now


def test_sqlite_never_links_on_an_unverified_email():
    s = SqliteStore(":memory:")
    google = s.find_or_create_user(ident("google", "g1", "jane@example.com"), utc_now())
    gh = s.find_or_create_user(ident("github", "42", "jane@example.com", verified=False), utc_now())
    assert gh.id != google.id and gh.email is None
    other = s.find_or_create_user(ident("github", "43", "jane@example.com"), utc_now())
    assert other.id == google.id  # a verified email links, even for a different GitHub account of the same person
