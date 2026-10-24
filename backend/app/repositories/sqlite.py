"""SQLite persistence (stdlib sqlite3). Reports are stored as JSON snapshots, so history and diffing
need no extra tables. All statements are parameterized."""
import datetime as dt
import sqlite3
import threading

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
CREATE TABLE IF NOT EXISTS saved(
  user_id TEXT NOT NULL,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  saved_at TEXT NOT NULL, PRIMARY KEY(user_id, opportunity_id));
"""


def sqlite_path(database_url: str) -> str:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or len(database_url) == len(prefix):
        raise ValueError("database_url must look like sqlite:///path/to/file.db")
    return database_url[len(prefix):]


def _ts(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # fixed width: sortable


def _parse(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=dt.timezone.utc)


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class SqliteStore:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.RLock()  # FastAPI runs sync routes in a thread pool
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- opportunities
    def save_opportunity(self, o: Opportunity) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO opportunities(id,title,organization,category,updated_at,data) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, organization=excluded.organization, "
                "category=excluded.category, updated_at=excluded.updated_at, data=excluded.data",
                (o.id, o.title, o.organization, o.category.value, _ts(o.updated_at), o.model_dump_json()))

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        with self._lock:
            row = self._conn.execute("SELECT data FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        return Opportunity.model_validate_json(row[0]) if row else None

    def list_opportunities(self, *, q: str | None = None, category: str | None = None,
                           limit: int = 20, offset: int = 0) -> list[Opportunity]:
        sql, args = "SELECT data FROM opportunities WHERE 1=1", []
        if q:
            sql += " AND (title LIKE ? ESCAPE '\\' OR organization LIKE ? ESCAPE '\\')"
            args += [_like(q), _like(q)]
        if category:
            sql += " AND category=?"
            args.append(category)
        sql += " ORDER BY updated_at DESC, id LIMIT ? OFFSET ?"
        with self._lock:
            rows = self._conn.execute(sql, [*args, limit, offset]).fetchall()
        return [Opportunity.model_validate_json(r[0]) for r in rows]

    # --- reports (snapshots)
    def save_report(self, r: VerificationReport) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO reports(run_id,opportunity_id,generated_at,data) VALUES(?,?,?,?)",
                               (r.run_id, r.opportunity_id, _ts(r.generated_at), r.model_dump_json()))

    def list_reports(self, opportunity_id: str, limit: int = 20) -> list[VerificationReport]:
        """Newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT data FROM reports WHERE opportunity_id=? ORDER BY generated_at DESC, run_id DESC LIMIT ?",
                (opportunity_id, limit)).fetchall()
        return [VerificationReport.model_validate_json(r[0]) for r in rows]

    def get_latest_report(self, opportunity_id: str) -> VerificationReport | None:
        reports = self.list_reports(opportunity_id, 1)
        return reports[0] if reports else None

    # --- saved
    def set_saved(self, user_id: str, opportunity_id: str, now: dt.datetime) -> dt.datetime:
        """Idempotent: saving again keeps the original saved_at."""
        with self._lock, self._conn:
            self._conn.execute("INSERT OR IGNORE INTO saved(user_id,opportunity_id,saved_at) VALUES(?,?,?)",
                               (user_id, opportunity_id, _ts(now)))
            row = self._conn.execute("SELECT saved_at FROM saved WHERE user_id=? AND opportunity_id=?",
                                     (user_id, opportunity_id)).fetchone()
        return _parse(row[0])

    def unset_saved(self, user_id: str, opportunity_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM saved WHERE user_id=? AND opportunity_id=?", (user_id, opportunity_id))

    def list_saved(self, user_id: str) -> list[tuple[Opportunity, dt.datetime]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT o.data, s.saved_at FROM saved s JOIN opportunities o ON o.id=s.opportunity_id "
                "WHERE s.user_id=? ORDER BY s.saved_at DESC, o.id", (user_id,)).fetchall()
        return [(Opportunity.model_validate_json(d), _parse(t)) for d, t in rows]