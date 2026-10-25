"""Chooses the persistence backend from VERIFAI_DATABASE_URL.

  sqlite:///./verifai.db                      -> SqliteStore (local development)
  postgresql://user:pass@host/db?sslmode=require -> PostgresStore (Neon or any Postgres)
"""
from app.repositories.base import Store


def make_store(database_url: str) -> Store:
    from app.repositories.postgres import is_postgres_url

    if is_postgres_url(database_url):
        from app.repositories.postgres import PostgresStore  # imported lazily: psycopg is only needed here

        return PostgresStore(database_url)
    from app.repositories.sqlite import SqliteStore, sqlite_path

    return SqliteStore(sqlite_path(database_url))
