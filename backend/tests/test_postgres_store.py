"""PostgresStore integration tests.

These tests require a real PostgreSQL database.  Set TEST_POSTGRES_URL to a valid
connection string to enable them:

    TEST_POSTGRES_URL=postgresql://user:pass@host/dbname?sslmode=require pytest tests/test_postgres_store.py -v

For Neon: use the direct (non-pooled) connection string from the Neon console.
Tests are automatically skipped when TEST_POSTGRES_URL is not set.

Each test gets a fresh set of tables (all rows deleted before the test, not dropped,
so the schema only needs to be created once per session).
"""
import datetime as dt
import os
import uuid

import pytest

from app.auth.models import ProviderIdentity
from app.repositories.postgres import PostgresStore
from app.schemas.enums import OpportunityCategory, OpportunityStatus
from app.schemas.opportunity import Opportunity

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Skip entire module when no Postgres URL is given
# ---------------------------------------------------------------------------
PG_URL = os.environ.get("TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL not set")


# ---------------------------------------------------------------------------
# Session-scoped store (one pool for all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pg_store():
    store = PostgresStore(PG_URL, min_size=1, max_size=3)
    yield store
    store.close()


@pytest.fixture(autouse=True)
def clean_tables(pg_store):
    """Wipe all rows before each test so tests are isolated."""
    with pg_store._pool.connection() as conn:
        conn.execute("DELETE FROM profiles")
        conn.execute("DELETE FROM saved")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM oauth_states")
        conn.execute("DELETE FROM oauth_identities")
        conn.execute("DELETE FROM reports")
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM opportunities")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def opp(title="SWE Intern", org="Acme", cat=OpportunityCategory.internship):
    oid = "opp_" + uuid.uuid4().hex[:12]
    return Opportunity(
        id=oid, title=title, organization=org, category=cat,
        canonical_url="https://acme.example.com/jobs",
        created_at=NOW, updated_at=NOW,
    )


def ident(provider, subject, email, verified=True):
    return ProviderIdentity(
        provider=provider, subject=subject, email=email,
        email_verified=verified, display_name="Test User",
    )


# ---------------------------------------------------------------------------
# Opportunity tests
# ---------------------------------------------------------------------------

def test_save_and_get_opportunity(pg_store):
    o = opp()
    pg_store.save_opportunity(o)
    got = pg_store.get_opportunity(o.id)
    assert got is not None
    assert got.id == o.id and got.title == o.title


def test_get_opportunity_not_found_returns_none(pg_store):
    assert pg_store.get_opportunity("nonexistent") is None


def test_upsert_updates_existing_opportunity(pg_store):
    o = opp(title="Original")
    pg_store.save_opportunity(o)
    updated = o.model_copy(update={"title": "Updated", "updated_at": NOW + dt.timedelta(hours=1)})
    pg_store.save_opportunity(updated)
    got = pg_store.get_opportunity(o.id)
    assert got.title == "Updated"


def test_list_opportunities_empty(pg_store):
    assert pg_store.list_opportunities() == []


def test_list_opportunities_with_query(pg_store):
    pg_store.save_opportunity(opp(title="Machine Learning Intern", org="DeepCo"))
    pg_store.save_opportunity(opp(title="Web Developer", org="WebCo"))
    results = pg_store.list_opportunities(q="Machine Learning")
    assert len(results) == 1 and "Machine Learning" in results[0].title


def test_list_opportunities_with_category_filter(pg_store):
    pg_store.save_opportunity(opp(cat=OpportunityCategory.internship))
    pg_store.save_opportunity(opp(cat=OpportunityCategory.fellowship))
    assert len(pg_store.list_opportunities(category="internship")) == 1
    assert len(pg_store.list_opportunities(category="fellowship")) == 1


def test_list_opportunities_pagination(pg_store):
    for i in range(5):
        pg_store.save_opportunity(opp(title=f"Role {i}"))
    page1 = pg_store.list_opportunities(limit=3, offset=0)
    page2 = pg_store.list_opportunities(limit=3, offset=3)
    assert len(page1) == 3 and len(page2) == 2


# ---------------------------------------------------------------------------
# Saved items
# ---------------------------------------------------------------------------

def test_set_and_list_saved(pg_store):
    o = opp()
    pg_store.save_opportunity(o)
    user = pg_store.find_or_create_user(ident("google", "g1", "alice@test.com"), NOW)
    pg_store.set_saved(user.id, o.id, NOW)
    saved = pg_store.list_saved(user.id)
    assert len(saved) == 1 and saved[0][0].id == o.id


def test_set_saved_is_idempotent(pg_store):
    o = opp()
    pg_store.save_opportunity(o)
    user = pg_store.find_or_create_user(ident("google", "g2", "bob@test.com"), NOW)
    t1 = pg_store.set_saved(user.id, o.id, NOW)
    t2 = pg_store.set_saved(user.id, o.id, NOW + dt.timedelta(days=1))
    assert t1 == t2  # saved_at is preserved


def test_unset_saved(pg_store):
    o = opp()
    pg_store.save_opportunity(o)
    user = pg_store.find_or_create_user(ident("google", "g3", "carol@test.com"), NOW)
    pg_store.set_saved(user.id, o.id, NOW)
    pg_store.unset_saved(user.id, o.id)
    assert pg_store.list_saved(user.id) == []


# ---------------------------------------------------------------------------
# Auth — users, sessions, OAuth state
# ---------------------------------------------------------------------------

def test_find_or_create_user_new(pg_store):
    user = pg_store.find_or_create_user(ident("google", "g10", "dan@test.com"), NOW)
    assert user.email == "dan@test.com" and user.email_verified is True
    assert "google" in user.providers


def test_find_or_create_user_existing_identity(pg_store):
    u1 = pg_store.find_or_create_user(ident("google", "g11", "eve@test.com"), NOW)
    u2 = pg_store.find_or_create_user(ident("google", "g11", "eve@test.com"), NOW)
    assert u1.id == u2.id


def test_find_or_create_user_links_by_verified_email(pg_store):
    google = pg_store.find_or_create_user(ident("google", "g12", "frank@test.com"), NOW)
    github = pg_store.find_or_create_user(ident("github", "gh42", "frank@test.com"), NOW)
    assert github.id == google.id
    assert set(github.providers) == {"google", "github"}


def test_find_or_create_user_does_not_link_unverified_email(pg_store):
    google = pg_store.find_or_create_user(ident("google", "g13", "grace@test.com"), NOW)
    github = pg_store.find_or_create_user(
        ident("github", "gh43", "grace@test.com", verified=False), NOW
    )
    assert github.id != google.id
    assert github.email is None  # unverified email not stored


def test_get_user_by_email_returns_verified_users_only(pg_store):
    pg_store.find_or_create_user(ident("google", "g14", "henry@test.com"), NOW)
    found = pg_store.get_user_by_email("henry@test.com")
    assert found is not None and found.email == "henry@test.com"
    assert pg_store.get_user_by_email("unknown@test.com") is None


def test_session_lifecycle(pg_store):
    user = pg_store.find_or_create_user(ident("google", "g20", "ivan@test.com"), NOW)
    token_hash = "hash_" + uuid.uuid4().hex
    expires = NOW + dt.timedelta(days=7)
    pg_store.create_session(token_hash, user.id, NOW, expires)
    assert pg_store.get_session_user_id(token_hash, NOW) == user.id
    pg_store.delete_session(token_hash)
    assert pg_store.get_session_user_id(token_hash, NOW) is None


def test_expired_session_is_purged(pg_store):
    user = pg_store.find_or_create_user(ident("google", "g21", "julia@test.com"), NOW)
    token_hash = "hash_" + uuid.uuid4().hex
    expired_at = NOW - dt.timedelta(seconds=1)
    pg_store.create_session(token_hash, user.id, NOW, expired_at)
    # Checking with a time after expiry should delete it and return None
    assert pg_store.get_session_user_id(token_hash, NOW + dt.timedelta(seconds=5)) is None


def test_oauth_state_pop_is_single_use(pg_store):
    state_hash = "sh_" + uuid.uuid4().hex
    pg_store.save_oauth_state(state_hash, "google", "nonce123", "verifier456",
                              "/dashboard", NOW + dt.timedelta(minutes=10))
    state1 = pg_store.pop_oauth_state(state_hash, NOW)
    state2 = pg_store.pop_oauth_state(state_hash, NOW)
    assert state1 is not None and state1.provider == "google"
    assert state2 is None  # already consumed


def test_oauth_state_expired_is_rejected(pg_store):
    state_hash = "sh_" + uuid.uuid4().hex
    past = NOW - dt.timedelta(minutes=1)
    pg_store.save_oauth_state(state_hash, "google", "n", "v", "/", past)
    assert pg_store.pop_oauth_state(state_hash, NOW) is None


def test_purge_expired_auth(pg_store):
    user = pg_store.find_or_create_user(ident("google", "g30", "kim@test.com"), NOW)
    old_tok = "hash_" + uuid.uuid4().hex
    pg_store.create_session(old_tok, user.id, NOW, NOW - dt.timedelta(seconds=1))
    pg_store.purge_expired_auth(NOW)
    assert pg_store.get_session_user_id(old_tok, NOW) is None


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def test_get_profile_returns_none_when_not_set(pg_store):
    user = pg_store.find_or_create_user(ident("google", "g40", "leo@test.com"), NOW)
    assert pg_store.get_profile(user.id) is None


def test_set_and_get_profile(pg_store):
    user = pg_store.find_or_create_user(ident("google", "g41", "mia@test.com"), NOW)
    profile = {"location": "Bengaluru", "interests": ["ML", "robotics"], "experience_years": 2}
    pg_store.set_profile(user.id, profile)
    got = pg_store.get_profile(user.id)
    assert got == profile


def test_set_profile_overwrites_existing(pg_store):
    user = pg_store.find_or_create_user(ident("google", "g42", "noah@test.com"), NOW)
    pg_store.set_profile(user.id, {"interests": ["AI"]})
    pg_store.set_profile(user.id, {"interests": ["Robotics"], "location": "Delhi"})
    got = pg_store.get_profile(user.id)
    assert got["location"] == "Delhi" and "Robotics" in got["interests"]


# ---------------------------------------------------------------------------
# Readiness probe (used by /health/ready)
# ---------------------------------------------------------------------------

def test_list_opportunities_with_limit_zero_for_readiness_probe(pg_store):
    """GET /health/ready calls list_opportunities(limit=0) — must not raise."""
    result = pg_store.list_opportunities(limit=0)
    assert result == []
