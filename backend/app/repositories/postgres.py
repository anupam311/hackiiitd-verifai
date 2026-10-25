"""PostgreSQL persistence (psycopg 3 + connection pool), intended for Neon.

Same behaviour as `SqliteStore` (see sqlite.py): reports are stored as JSON snapshots, timestamps are
stored as fixed-width UTC text so they sort correctly, every statement is parameterized.

Neon notes:
- Use the connection string from the Neon console (it already contains `sslmode=require`).
- The *pooled* host (`-pooler`) runs PgBouncer in transaction mode, which does not support server-side
  prepared statements. `prepare_threshold=None` below disables them, so both pooled and direct hosts work.
- Neon suspends idle compute; the pool checks connections before handing them out and recycles idle ones,
  so the first request after a pause reconnects instead of failing.
"""
import datetime as dt
import json
import uuid
from typing import Any

from psycopg_pool import ConnectionPool

from app.auth.models import OAuthState, ProviderIdentity, User
from app.report.models import VerificationReport
from app.schemas.opportunity import Opportunity

_SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, organization TEXT NOT NULL, category TEXT NOT NULL,
  updated_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reports(
  run_id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  generated_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_reports_opp ON reports(opportunity_id, generated_at DESC);
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, email TEXT, email_verified INTEGER NOT NULL DEFAULT 0, display_name TEXT,
  avatar_url TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_identities(
  provider TEXT NOT NULL, subject TEXT NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at TEXT NOT NULL,
  PRIMARY KEY(provider, subject));
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_states(
  state_hash TEXT PRIMARY KEY, provider TEXT NOT NULL, nonce TEXT NOT NULL, code_verifier TEXT NOT NULL,
  next_path TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS saved(
  user_id TEXT NOT NULL,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  saved_at TEXT NOT NULL, PRIMARY KEY(user_id, opportunity_id));
CREATE TABLE IF NOT EXISTS profiles(
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  data TEXT NOT NULL);
"""


def is_postgres_url(database_url: str) -> bool:
    return database_url.startswith(("postgres://", "postgresql://"))


def _ts(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # fixed width: sortable


def _parse(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=dt.timezone.utc)


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class PostgresStore:
    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 5):
        self._pool = ConnectionPool(
            database_url, min_size=min_size, max_size=max_size, open=False,
            check=ConnectionPool.check_connection,  # drop connections Neon closed while the compute slept
            max_idle=240, kwargs={"prepare_threshold": None})  # no prepared statements: PgBouncer-safe
        self._pool.open(wait=True, timeout=60)  # first connect can wake a suspended Neon compute
        with self._pool.connection() as conn:
            conn.execute(_SCHEMA)

    def close(self) -> None:
        self._pool.close()

    # --- opportunities
    def save_opportunity(self, o: Opportunity) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO opportunities(id,title,organization,category,updated_at,data) VALUES(%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, organization=excluded.organization, "
                "category=excluded.category, updated_at=excluded.updated_at, data=excluded.data",
                (o.id, o.title, o.organization, o.category.value, _ts(o.updated_at), o.model_dump_json()))

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT data FROM opportunities WHERE id=%s", (opportunity_id,)).fetchone()
        return Opportunity.model_validate_json(row[0]) if row else None

    def list_opportunities(self, *, q: str | None = None, category: str | None = None,
                           limit: int = 20, offset: int = 0) -> list[Opportunity]:
        sql, args = "SELECT data FROM opportunities WHERE TRUE", []
        if q:
            sql += " AND (title ILIKE %s ESCAPE '\\' OR organization ILIKE %s ESCAPE '\\')"
            args += [_like(q), _like(q)]
        if category:
            sql += " AND category=%s"
            args.append(category)
        sql += " ORDER BY updated_at DESC, id LIMIT %s OFFSET %s"
        with self._pool.connection() as conn:
            rows = conn.execute(sql, [*args, limit, offset]).fetchall()
        return [Opportunity.model_validate_json(r[0]) for r in rows]

    # --- reports (snapshots)
    def save_report(self, r: VerificationReport) -> None:
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO reports(run_id,opportunity_id,generated_at,data) VALUES(%s,%s,%s,%s)",
                         (r.run_id, r.opportunity_id, _ts(r.generated_at), r.model_dump_json()))

    def list_reports(self, opportunity_id: str, limit: int = 20) -> list[VerificationReport]:
        """Newest first."""
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT data FROM reports WHERE opportunity_id=%s ORDER BY generated_at DESC, run_id DESC LIMIT %s",
                (opportunity_id, limit)).fetchall()
        return [VerificationReport.model_validate_json(r[0]) for r in rows]

    def get_latest_report(self, opportunity_id: str) -> VerificationReport | None:
        reports = self.list_reports(opportunity_id, 1)
        return reports[0] if reports else None

    # --- saved
    def set_saved(self, user_id: str, opportunity_id: str, now: dt.datetime) -> dt.datetime:
        """Idempotent: saving again keeps the original saved_at."""
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO saved(user_id,opportunity_id,saved_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                         (user_id, opportunity_id, _ts(now)))
            row = conn.execute("SELECT saved_at FROM saved WHERE user_id=%s AND opportunity_id=%s",
                               (user_id, opportunity_id)).fetchone()
        return _parse(row[0])

    def unset_saved(self, user_id: str, opportunity_id: str) -> None:
        with self._pool.connection() as conn:
            conn.execute("DELETE FROM saved WHERE user_id=%s AND opportunity_id=%s", (user_id, opportunity_id))

    def list_saved(self, user_id: str) -> list[tuple[Opportunity, dt.datetime]]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT o.data, s.saved_at FROM saved s JOIN opportunities o ON o.id=s.opportunity_id "
                "WHERE s.user_id=%s ORDER BY s.saved_at DESC, o.id", (user_id,)).fetchall()
        return [(Opportunity.model_validate_json(d), _parse(t)) for d, t in rows]

    # --- auth: users, sessions, OAuth state. Raw tokens are never stored, only their SHA-256 hashes.
    def get_user(self, user_id: str) -> User | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT id,email,email_verified,display_name,avatar_url,created_at FROM users WHERE id=%s",
                (user_id,)).fetchone()
            providers = [r[0] for r in conn.execute(
                "SELECT provider FROM oauth_identities WHERE user_id=%s ORDER BY provider", (user_id,)).fetchall()]
        if not row:
            return None
        return User(id=row[0], email=row[1], email_verified=bool(row[2]), display_name=row[3],
                    avatar_url=row[4], created_at=_parse(row[5]), providers=providers)

    def find_or_create_user(self, identity: ProviderIdentity, now: dt.datetime) -> User:
        """Existing (provider, subject) -> that user. Otherwise, if the provider verified an email that
        belongs to an existing verified-email user, link to that user (never by an unverified email).
        Otherwise a new user. The email is kept only when the provider says it is verified."""
        with self._pool.connection() as conn:  # one transaction: committed when the block exits
            row = conn.execute("SELECT user_id FROM oauth_identities WHERE provider=%s AND subject=%s",
                               (identity.provider, identity.subject)).fetchone()
            match = None
            if not row and identity.email and identity.email_verified:
                match = conn.execute(
                    "SELECT id FROM users WHERE lower(email)=lower(%s) AND email_verified=TRUE "
                    "ORDER BY created_at LIMIT 1", (identity.email,)).fetchone()
            if row:
                user_id = row[0]
            elif match:
                user_id = match[0]
                conn.execute("INSERT INTO oauth_identities(provider,subject,user_id,created_at) VALUES(%s,%s,%s,%s) "
                             "ON CONFLICT DO NOTHING", (identity.provider, identity.subject, user_id, _ts(now)))
            else:
                user_id = "usr_" + uuid.uuid4().hex[:16]
                email = identity.email if identity.email_verified and identity.email else None
                conn.execute(
                    "INSERT INTO users(id,email,email_verified,display_name,avatar_url,created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (user_id, email, int(email is not None), identity.display_name, identity.avatar_url, _ts(now)))
                conn.execute("INSERT INTO oauth_identities(provider,subject,user_id,created_at) VALUES(%s,%s,%s,%s)",
                             (identity.provider, identity.subject, user_id, _ts(now)))
        return self.get_user(user_id)  # type: ignore[return-value]

    def get_user_by_email(self, email: str) -> User | None:
        """Find a verified-email user. Only users whose email_verified=TRUE are returned."""
        with self._pool.connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE lower(email)=lower(%s) AND email_verified=TRUE",
                               (email,)).fetchone()
        return self.get_user(row[0]) if row else None

    def link_oauth_identity(self, provider: str, subject: str, user_id: str, now: dt.datetime) -> None:
        """Link an additional OAuth identity to an existing user (account-linking safeguard)."""
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO oauth_identities(provider,subject,user_id,created_at) VALUES(%s,%s,%s,%s) "
                         "ON CONFLICT DO NOTHING", (provider, subject, user_id, _ts(now)))

    def create_session(self, token_hash: str, user_id: str, now: dt.datetime, expires_at: dt.datetime) -> None:
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES(%s,%s,%s,%s)",
                         (token_hash, user_id, _ts(now), _ts(expires_at)))

    def get_session_user_id(self, token_hash: str, now: dt.datetime) -> str | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT user_id, expires_at FROM sessions WHERE token_hash=%s",
                               (token_hash,)).fetchone()
            if row and row[1] <= _ts(now):  # expired: remove it
                conn.execute("DELETE FROM sessions WHERE token_hash=%s", (token_hash,))
                return None
        return row[0] if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._pool.connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=%s", (token_hash,))

    def save_oauth_state(self, state_hash: str, provider: str, nonce: str, code_verifier: str,
                         next_path: str, expires_at: dt.datetime) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO oauth_states(state_hash,provider,nonce,code_verifier,next_path,expires_at) "
                "VALUES(%s,%s,%s,%s,%s,%s)", (state_hash, provider, nonce, code_verifier, next_path, _ts(expires_at)))

    def pop_oauth_state(self, state_hash: str, now: dt.datetime) -> OAuthState | None:
        """Single use: the row is deleted whether or not it is still valid. DELETE ... RETURNING is atomic,
        so two concurrent callbacks with the same state cannot both succeed."""
        with self._pool.connection() as conn:
            row = conn.execute(
                "DELETE FROM oauth_states WHERE state_hash=%s "
                "RETURNING provider,nonce,code_verifier,next_path,expires_at", (state_hash,)).fetchone()
        if not row or row[4] <= _ts(now):
            return None
        return OAuthState(provider=row[0], nonce=row[1], code_verifier=row[2], next_path=row[3])

    def purge_expired_auth(self, now: dt.datetime) -> None:
        with self._pool.connection() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at<=%s", (_ts(now),))
            conn.execute("DELETE FROM oauth_states WHERE expires_at<=%s", (_ts(now),))

    # --- profile
    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT data FROM profiles WHERE user_id=%s", (user_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def set_profile(self, user_id: str, data: dict[str, Any]) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO profiles(user_id,data) VALUES(%s,%s) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data",
                (user_id, json.dumps(data)))
