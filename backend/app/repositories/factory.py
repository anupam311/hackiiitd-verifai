"""Chooses the persistence backend from VERIFAI_DATABASE_URL.

  sqlite:///./verifai.db                         -> SqliteStore  (local development)
  sqlite:///:memory:                             -> SqliteStore  (tests)
  postgresql://user:pass@host/db?sslmode=require -> PostgresStore (Neon or any Postgres)
  postgres://...                                 -> PostgresStore (same, alternate scheme)

Import cost: psycopg / psycopg_pool are only imported when a Postgres URL is detected.
"""
from app.repositories.base import Store


def make_store(database_url: str, *, pool_size: int = 5) -> Store:
    if database_url.startswith(("postgres://", "postgresql://")):
        from app.repositories.postgres import PostgresStore  # lazy: psycopg only needed here

        return PostgresStore(database_url, min_size=1, max_size=pool_size)

    from app.repositories.sqlite import SqliteStore, sqlite_path

    return SqliteStore(sqlite_path(database_url))
