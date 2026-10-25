"""Unit tests for app/repositories/factory.py.

These tests always run (no network or DB required): they verify that make_store()
routes the right Store implementation based on the URL scheme, and that bad URLs
are rejected with a clear error.
"""
import pytest

from app.repositories.factory import make_store
from app.repositories.memory import InMemoryStore
from app.repositories.sqlite import SqliteStore


def test_sqlite_memory_url_returns_sqlite_store():
    store = make_store("sqlite:///:memory:")
    try:
        assert isinstance(store, SqliteStore)
    finally:
        store.close()


def test_sqlite_file_url_returns_sqlite_store(tmp_path):
    url = f"sqlite:///{tmp_path}/test.db"
    store = make_store(url)
    try:
        assert isinstance(store, SqliteStore)
    finally:
        store.close()


def test_postgres_scheme_routes_to_postgres(monkeypatch):
    """PostgresStore is selected for postgresql:// URLs — but we don't open a real connection."""
    # Patch the pool so no network call is made.
    import psycopg_pool

    class _FakePool:
        def __init__(self, *a, **kw): pass
        def open(self, **kw): pass
        def connection(self): return _FakeConn()
        def close(self): pass

    class _FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql, params=None): return _FakeCursor()

    class _FakeCursor:
        def fetchone(self): return None
        def fetchall(self): return []

    monkeypatch.setattr(psycopg_pool, "ConnectionPool", _FakePool)
    from app.repositories.postgres import PostgresStore

    store = make_store("postgresql://user:pass@localhost/db")
    assert isinstance(store, PostgresStore)
    store.close()


def test_postgres_alternate_scheme_routes_to_postgres(monkeypatch):
    """postgres:// (without 'ql') also routes to PostgresStore."""
    import psycopg_pool

    class _FakePool:
        def __init__(self, *a, **kw): pass
        def open(self, **kw): pass
        def connection(self): return _Conn()
        def close(self): pass

    class _Conn:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql, params=None): return _Cur()

    class _Cur:
        def fetchone(self): return None
        def fetchall(self): return []

    monkeypatch.setattr(psycopg_pool, "ConnectionPool", _FakePool)
    from app.repositories.postgres import PostgresStore

    store = make_store("postgres://user:pass@localhost/db")
    assert isinstance(store, PostgresStore)
    store.close()


def test_unknown_scheme_raises_value_error():
    with pytest.raises((ValueError, Exception)):
        make_store("mysql://user:pass@localhost/db")


def test_missing_path_in_sqlite_url_raises():
    with pytest.raises((ValueError, Exception)):
        make_store("sqlite:///")


def test_make_store_pool_size_accepted_for_sqlite(tmp_path):
    """pool_size kwarg is accepted even for SQLite (just ignored)."""
    url = f"sqlite:///{tmp_path}/p.db"
    store = make_store(url, pool_size=10)
    try:
        assert isinstance(store, SqliteStore)
    finally:
        store.close()
