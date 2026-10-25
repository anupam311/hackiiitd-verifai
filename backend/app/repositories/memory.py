"""Pure in-memory Store implementation used in tests only.

Satisfies the same protocol as SqliteStore without touching the filesystem.
Not thread-safe (tests are single-threaded) and not suitable for production.
"""
import datetime as dt
import threading
from typing import Any

from app.auth.models import OAuthState, ProviderIdentity, User
from app.report.models import VerificationReport
from app.schemas.opportunity import Opportunity


class InMemoryStore:
    """Thread-safe in-memory store for testing.  No disk I/O, no external deps."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._opportunities: dict[str, Opportunity] = {}
        self._reports: dict[str, list[VerificationReport]] = {}  # opportunity_id -> newest-first
        self._saved: dict[tuple[str, str], dt.datetime] = {}  # (user_id, opp_id) -> saved_at
        self._users: dict[str, User] = {}  # user_id -> User
        self._oauth_identities: dict[tuple[str, str], str] = {}  # (provider, subject) -> user_id
        self._sessions: dict[str, tuple[str, dt.datetime]] = {}  # token_hash -> (user_id, expires_at)
        self._oauth_states: dict[str, tuple[OAuthState, dt.datetime]] = {}  # state_hash -> (state, expires_at)
        self._profiles: dict[str, dict[str, Any]] = {}  # user_id -> profile dict

    def close(self) -> None:  # no-op for in-memory store
        pass

    # --- opportunities ---
    def save_opportunity(self, o: Opportunity) -> None:
        with self._lock:
            self._opportunities[o.id] = o

    def get_opportunity(self, opportunity_id: str) -> Opportunity | None:
        with self._lock:
            return self._opportunities.get(opportunity_id)

    def list_opportunities(self, *, q: str | None = None, category: str | None = None,
                           limit: int = 20, offset: int = 0) -> list[Opportunity]:
        with self._lock:
            items = list(self._opportunities.values())
        # filter
        if q:
            ql = q.lower()
            items = [o for o in items if ql in o.title.lower() or ql in o.organization.lower()]
        if category:
            items = [o for o in items if o.category.value == category]
        # sort newest first (updated_at DESC, id)
        items.sort(key=lambda o: (-o.updated_at.timestamp(), o.id))
        return items[offset: offset + limit]

    # --- reports ---
    def save_report(self, r: VerificationReport) -> None:
        with self._lock:
            if r.opportunity_id not in self._opportunities:
                raise ValueError(f"Opportunity {r.opportunity_id!r} not found; save it first")
            bucket = self._reports.setdefault(r.opportunity_id, [])
            if any(rep.run_id == r.run_id for rep in bucket):
                raise ValueError(f"Duplicate run_id {r.run_id!r}")
            bucket.insert(0, r)  # newest-first
            bucket.sort(key=lambda rep: (-rep.generated_at.timestamp(), rep.run_id))

    def list_reports(self, opportunity_id: str, limit: int = 20) -> list[VerificationReport]:
        with self._lock:
            return list(self._reports.get(opportunity_id, []))[:limit]

    def get_latest_report(self, opportunity_id: str) -> VerificationReport | None:
        reports = self.list_reports(opportunity_id, 1)
        return reports[0] if reports else None

    # --- saved ---
    def set_saved(self, user_id: str, opportunity_id: str, now: dt.datetime) -> dt.datetime:
        """Idempotent: keeps the original saved_at."""
        with self._lock:
            key = (user_id, opportunity_id)
            if key not in self._saved:
                self._saved[key] = now
            return self._saved[key]

    def unset_saved(self, user_id: str, opportunity_id: str) -> None:
        with self._lock:
            self._saved.pop((user_id, opportunity_id), None)

    def list_saved(self, user_id: str) -> list[tuple[Opportunity, dt.datetime]]:
        with self._lock:
            pairs = [(k[1], v) for k, v in self._saved.items() if k[0] == user_id]
        pairs.sort(key=lambda p: (-p[1].timestamp(), p[0]))
        result = []
        for opp_id, saved_at in pairs:
            opp = self.get_opportunity(opp_id)
            if opp is not None:
                result.append((opp, saved_at))
        return result

    # --- auth: users, sessions, OAuth state ---
    def get_user(self, user_id: str) -> User | None:
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        with self._lock:
            for user in self._users.values():
                if user.email and user.email.lower() == email.lower() and user.email_verified:
                    return user
        return None

    def find_or_create_user(self, identity: ProviderIdentity, now: dt.datetime) -> User:
        import uuid
        with self._lock:
            key = (identity.provider, identity.subject)
            if key in self._oauth_identities:
                return self._users[self._oauth_identities[key]]
            # Account-linking: if a verified email matches an existing user, link the identity.
            if identity.email and identity.email_verified:
                existing = self.get_user_by_email(identity.email)
                if existing is not None:
                    self._oauth_identities[key] = existing.id
                    self._users[existing.id] = User(
                        id=existing.id, email=existing.email,
                        email_verified=existing.email_verified,
                        display_name=existing.display_name, avatar_url=existing.avatar_url,
                        created_at=existing.created_at,
                        providers=sorted(existing.providers + [identity.provider]))
                    return self._users[existing.id]
            user_id = "usr_" + uuid.uuid4().hex[:16]
            email = identity.email if identity.email_verified and identity.email else None
            user = User(id=user_id, email=email, email_verified=email is not None,
                        display_name=identity.display_name, avatar_url=identity.avatar_url,
                        created_at=now, providers=[identity.provider])
            self._users[user_id] = user
            self._oauth_identities[key] = user_id
            return user

    def link_oauth_identity(self, provider: str, subject: str, user_id: str, now: dt.datetime) -> None:
        """Add a new (provider, subject) mapping to an existing user (account linking)."""
        with self._lock:
            self._oauth_identities[(provider, subject)] = user_id
            existing = self._users.get(user_id)
            if existing and provider not in existing.providers:
                self._users[user_id] = User(
                    id=existing.id, email=existing.email, email_verified=existing.email_verified,
                    display_name=existing.display_name, avatar_url=existing.avatar_url,
                    created_at=existing.created_at,
                    providers=sorted(existing.providers + [provider]))

    def create_session(self, token_hash: str, user_id: str, now: dt.datetime, expires_at: dt.datetime) -> None:
        with self._lock:
            self._sessions[token_hash] = (user_id, expires_at)

    def get_session_user_id(self, token_hash: str, now: dt.datetime) -> str | None:
        with self._lock:
            entry = self._sessions.get(token_hash)
            if entry is None:
                return None
            user_id, expires_at = entry
            if expires_at <= now:
                del self._sessions[token_hash]
                return None
            return user_id

    def delete_session(self, token_hash: str) -> None:
        with self._lock:
            self._sessions.pop(token_hash, None)

    def save_oauth_state(self, state_hash: str, provider: str, nonce: str, code_verifier: str,
                         next_path: str, expires_at: dt.datetime) -> None:
        with self._lock:
            state = OAuthState(provider=provider, nonce=nonce, code_verifier=code_verifier,
                               next_path=next_path)
            self._oauth_states[state_hash] = (state, expires_at)

    def pop_oauth_state(self, state_hash: str, now: dt.datetime) -> OAuthState | None:
        """Single use: the record is removed whether or not it is still valid."""
        with self._lock:
            entry = self._oauth_states.pop(state_hash, None)
        if entry is None:
            return None
        state, expires_at = entry
        return None if expires_at <= now else state

    def purge_expired_auth(self, now: dt.datetime) -> None:
        with self._lock:
            expired_states = [k for k, (_, exp) in self._oauth_states.items() if exp <= now]
            for k in expired_states:
                del self._oauth_states[k]
            expired_sessions = [k for k, (_, exp) in self._sessions.items() if exp <= now]
            for k in expired_sessions:
                del self._sessions[k]

    # --- profile ---
    def get_profile(self, user_id: str) -> dict | None:
        with self._lock:
            return self._profiles.get(user_id)

    def set_profile(self, user_id: str, data: dict) -> None:
        with self._lock:
            self._profiles[user_id] = data
