"""SQLite storage layer: schema, connection handling, row -> dataclass mapping."""

import asyncio
import contextlib
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

from constants import DEFAULT_SETTINGS, get_logger
from models import (
    AppSettings,
    PushSubscription,
    ResetToken,
    Session,
    User,
    WeightEntry,
)
from rewards import reward_state

logger = get_logger("database")

# Sentinel owner for legacy single-user rows: 0 is not a real user id (users
# ids start at 1; legacy pre-auth rows are discarded during migration.

# One statement per element: init_schema runs each inside the explicit
# transaction (BEGIN) instead of executescript, which would implicitly COMMIT
# the open transaction and break the all-or-nothing boundary.
SCHEMA_STATEMENTS: tuple[str, ...] = (
    "DROP TABLE IF EXISTS reward_events;",
    # Every data table is owned by a user (user_id). Legacy single-user rows
    # migrate in with the sentinel 0 and are claimed by the first registrant.
    """
    CREATE TABLE IF NOT EXISTS weight_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 0,
        date TEXT NOT NULL,
        weight_kg REAL NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (user_id, date)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS push_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 0,
        endpoint TEXT NOT NULL UNIQUE,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS active_rewards (
        user_id INTEGER NOT NULL,
        checkpoint_percent INTEGER NOT NULL,
        threshold_kg REAL NOT NULL,
        earned_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, checkpoint_percent)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS notifications_sent (
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (user_id, date, type)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (user_id, key)
    );
    """,
    "DELETE FROM settings WHERE key = 'milestone_step_kg';",
    # ---- identity tables (user-accounts-auth) ----
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        email TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL
    );
    """,
    # ---- email password reset (password-reset) ----
    """
    CREATE TABLE IF NOT EXISTS reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL
    );
    """,
)

# Legacy (pre-auth) tables whose UNIQUE/PK constraints cannot be changed in
# place: rebuild via create `_new` -> discard rows -> drop old -> rename, all
# inside the caller's transaction. Legacy pre-auth rows are DISCARDED (they
# were smoke-test artifacts, not real per-user data); every new account starts
# fresh and sets its own target/height/schedules. The four table rebuilds
# mirror the target schema; push_subscriptions only needs the column
# (its endpoint stays globally UNIQUE) and is handled separately.
LEGACY_TABLE_REBUILDS: tuple[tuple[str, str, str], ...] = (
    (
        "weight_entries",
        """
        CREATE TABLE weight_entries_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (user_id, date)
        );
        """,
        "",  # legacy rows discarded — no copy
    ),
    (
        "active_rewards",
        """
        CREATE TABLE active_rewards_new (
            user_id INTEGER NOT NULL,
            checkpoint_percent INTEGER NOT NULL,
            threshold_kg REAL NOT NULL,
            earned_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, checkpoint_percent)
        );
        """,
        "",  # legacy rows discarded — no copy
    ),
    (
        "notifications_sent",
        """
        CREATE TABLE notifications_sent_new (
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            sent_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, date, type)
        );
        """,
        "",  # legacy rows discarded — no copy
    ),
    (
        "settings",
        """
        CREATE TABLE settings_new (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        );
        """,
        "",  # legacy rows discarded — no copy
    ),
)


class DuplicateUsernameError(Exception):
    """Raised when create_user hits the username UNIQUE constraint."""


class DuplicateEmailError(Exception):
    """Raised when a user/email insert or update hits the email UNIQUE index.

    Account recovery is only safe when an email belongs to exactly one account:
    a shared address would let one owner reset the other's password.
    """


class Database:
    """Thin wrapper around one SQLite connection, serialized by a lock.

    Lives on ``app.state.db``. All methods are synchronous; callers on the
    request path must wrap them with :func:`run_db` to stay async. Every
    user-owned query takes ``user_id`` as its first parameter so no call site
    can accidentally operate across users.
    """

    def __init__(self, db_path: str) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        logger.info("opened database at %s", db_path)

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    @contextlib.contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self.conn.execute("BEGIN")
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def init_schema(self) -> None:
        with self._tx() as conn:
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
            self._migrate_legacy_schema(conn)
            self._migrate_users_schema(conn)

    def _migrate_users_schema(self, conn: sqlite3.Connection) -> None:
        """Add the users.email column and its partial UNIQUE index to databases
        created before password-reset support. Idempotent: fresh schemas already
        carry the column, so the ALTER runs at most once; the index is
        create-if-missing. Runs inside the caller's transaction."""
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        # Partial index: non-NULL emails must be unique (account recovery is
        # only safe with exclusive email ownership); NULLs stay unlimited so
        # accounts that never set an email are unaffected.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email"
            " ON users(email) WHERE email IS NOT NULL"
        )

    def _migrate_legacy_schema(self, conn: sqlite3.Connection) -> None:
        """Rebuild pre-auth tables in place, DISCARDING legacy data. Runs
        inside the caller's transaction (all-or-nothing);
        idempotent — a migrated or fresh schema is left untouched."""
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(weight_entries)").fetchall()
        }
        if "user_id" in columns:
            return
        for table, create_sql, copy_sql in LEGACY_TABLE_REBUILDS:
            conn.execute(f"DROP TABLE IF EXISTS {table}_new")
            conn.execute(create_sql)
            if copy_sql:
                conn.execute(copy_sql)
            conn.execute(f"DROP TABLE {table}")
            conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
        conn.execute(
            "ALTER TABLE push_subscriptions"
            " ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0"
        )
        # Legacy pre-auth subscription rows have no owner and are discarded.
        conn.execute("DELETE FROM push_subscriptions WHERE user_id = 0")

    # ---- weight entries ----

    def list_entries(self, user_id: int) -> list[WeightEntry]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, weight_kg, created_at"
                " FROM weight_entries WHERE user_id = ? ORDER BY date DESC",
                (user_id,),
            ).fetchall()
        return [_weight_from_row(row) for row in rows]

    def get_entry_by_date(self, user_id: int, date: str) -> Optional[WeightEntry]:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id, date, weight_kg, created_at"
                " FROM weight_entries WHERE user_id = ? AND date = ?",
                (user_id, date),
            ).fetchone()
        return _weight_from_row(row) if row is not None else None

    def upsert_entry(self, user_id: int, date: str, weight_kg: float) -> WeightEntry:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO weight_entries (user_id, date, weight_kg, created_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(user_id, date) DO UPDATE SET weight_kg = excluded.weight_kg",
                (user_id, date, weight_kg, _local_now()),
            )
            row = conn.execute(
                "SELECT id, date, weight_kg, created_at"
                " FROM weight_entries WHERE user_id = ? AND date = ?",
                (user_id, date),
            ).fetchone()
            self._reconcile_active_rewards(conn, user_id)
        if row is None:
            raise RuntimeError("upsert produced no row")
        return _weight_from_row(row)

    def delete_entry(self, user_id: int, entry_id: int) -> bool:
        # Ownership check inside the DELETE: a cross-user id deletes nothing.
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM weight_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            )
            deleted = cursor.rowcount > 0
            self._reconcile_active_rewards(conn, user_id)
            return deleted

    # ---- active reward checkpoints ----

    REWARD_AFFECTING_KEYS: tuple[str, ...] = (
        "target_weight",
        "start_weight_override",
    )

    def reconcile_active_rewards(self) -> None:
        """Reconcile the persisted checkpoint set for every registered user in
        its own transaction (startup entry point after the schema is created)."""
        with self._tx() as conn:
            rows = conn.execute("SELECT id FROM users ORDER BY id").fetchall()
            for row in rows:
                self._reconcile_active_rewards(conn, int(row["id"]))

    def list_active_rewards(self, user_id: int) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT checkpoint_percent, threshold_kg, earned_at"
                " FROM active_rewards WHERE user_id = ? ORDER BY checkpoint_percent",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _reconcile_active_rewards(
        self, conn: sqlite3.Connection, user_id: int
    ) -> None:
        """Transactional core: sync one user's active_rewards to the derived
        checkpoint state using the caller's open transaction. Earned
        timestamps survive while a checkpoint stays active; revoked rows are
        removed and re-earned ones get a fresh local timestamp."""
        entry_rows = conn.execute(
            "SELECT id, date, weight_kg, created_at FROM weight_entries"
            " WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        entries = [_weight_from_row(row) for row in entry_rows]
        state = reward_state(entries, self._settings_from_conn(user_id, conn))
        existing = {
            row["checkpoint_percent"]
            for row in conn.execute(
                "SELECT checkpoint_percent FROM active_rewards WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        }
        derived = {cp.percent for cp in state.active}
        for percent in existing - derived:
            conn.execute(
                "DELETE FROM active_rewards WHERE user_id = ? AND checkpoint_percent = ?",
                (user_id, percent),
            )
        for cp in state.active:
            conn.execute(
                "INSERT INTO active_rewards"
                " (user_id, checkpoint_percent, threshold_kg, earned_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(user_id, checkpoint_percent) DO UPDATE SET"
                " threshold_kg = excluded.threshold_kg",
                (user_id, cp.percent, cp.threshold_kg, _local_now()),
            )

    # ---- identity: users ----

    def create_user(
        self,
        username: str,
        password_hash: str,
        salt: str,
        email: Optional[str] = None,
    ) -> User:
        """Insert a user; raise DuplicateUsernameError on a taken username and
        DuplicateEmailError on an email already owned by another account.

        Every account starts with an empty dataset; legacy pre-auth rows were
        discarded during migration, so there is no backfill to claim.
        """
        with self._tx() as conn:
            if email is not None and self._email_taken(conn, email):
                raise DuplicateEmailError(email)
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, salt, created_at, email)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (username, password_hash, salt, _utc_now(), email),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateUsernameError(username) from exc
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("user insert produced no row id")
            user_id = int(lastrowid)
            row = conn.execute(
                "SELECT id, username, password_hash, salt, created_at, email"
                " FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("user insert produced no row")
        return _user_from_row(row)

    @staticmethod
    def _email_taken(conn: sqlite3.Connection, email: str) -> bool:
        """Whether any user row already owns this email (partial-index check)."""
        row = conn.execute(
            "SELECT 1 FROM users WHERE email = ? LIMIT 1", (email,)
        ).fetchone()
        return row is not None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Fetch a user by its stored (lowercased) username."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, salt, created_at, email"
                " FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return _user_from_row(row) if row is not None else None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Fetch the user owning this (normalized, lowercased) email. The
        partial UNIQUE index guarantees at most one owner."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, salt, created_at, email"
                " FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        return _user_from_row(row) if row is not None else None

    def set_user_email(self, user_id: int, email: str) -> User:
        """Set (or replace) a user's email; raises DuplicateEmailError when the
        address is already owned by a different account. Returns the updated
        user."""
        with self._tx() as conn:
            taken = conn.execute(
                "SELECT 1 FROM users WHERE email = ? AND id != ? LIMIT 1",
                (email, user_id),
            ).fetchone()
            if taken is not None:
                raise DuplicateEmailError(email)
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
            row = conn.execute(
                "SELECT id, username, password_hash, salt, created_at, email"
                " FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("user update produced no row")
        return _user_from_row(row)

    def list_users(self) -> list[User]:
        """All users in registration order — the scheduler's iteration source."""
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, username, password_hash, salt, created_at, email"
                " FROM users ORDER BY id"
            ).fetchall()
        return [_user_from_row(row) for row in rows]

    # ---- identity: sessions ----

    def create_session(
        self, user_id: int, token_hash: str, expires_at: str
    ) -> Session:
        """Insert a session row, opportunistically sweeping expired ones first."""
        with self._tx() as conn:
            conn.execute(
                "DELETE FROM sessions WHERE expires_at <= ?", (_utc_now(),)
            )
            cursor = conn.execute(
                "INSERT INTO sessions (user_id, token_hash, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (user_id, token_hash, _utc_now(), expires_at),
            )
            row = conn.execute(
                "SELECT id, user_id, token_hash, created_at, expires_at"
                " FROM sessions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("session insert produced no row")
        return _session_from_row(row)

    def get_user_by_session(self, token_hash: str) -> Optional[User]:
        """Resolve a session token hash to its user, excluding expired rows."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT u.id, u.username, u.password_hash, u.salt, u.created_at, u.email"
                " FROM sessions s JOIN users u ON u.id = s.user_id"
                " WHERE s.token_hash = ? AND s.expires_at > ?",
                (token_hash, _utc_now()),
            ).fetchone()
        return _user_from_row(row) if row is not None else None

    def delete_session(self, token_hash: str) -> bool:
        """Revoke one session; return whether a row was removed."""
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (token_hash,)
            )
            return cursor.rowcount > 0

    def delete_sessions_for_user(self, user_id: int) -> int:
        """Revoke every session for a user (password reset, log out everywhere);
        return the number of rows removed."""
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE user_id = ?", (user_id,)
            )
            return cursor.rowcount

    def delete_expired_sessions(self, now: str) -> int:
        """Sweep sessions expired by the given UTC cutoff; return the count."""
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE expires_at <= ?", (now,)
            )
            return cursor.rowcount

    # ---- identity: password-reset tokens -------

    def create_reset_token(
        self, user_id: int, token_hash: str, expires_at: str
    ) -> ResetToken:
        """Insert a one-time reset token, opportunistically sweeping expired
        ones first (same pattern as create_session)."""
        with self._tx() as conn:
            conn.execute(
                "DELETE FROM reset_tokens WHERE expires_at <= ?", (_utc_now(),)
            )
            cursor = conn.execute(
                "INSERT INTO reset_tokens (user_id, token_hash, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (user_id, token_hash, _utc_now(), expires_at),
            )
            row = conn.execute(
                "SELECT id, user_id, token_hash, created_at, expires_at"
                " FROM reset_tokens WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("reset token insert produced no row")
        return _reset_token_from_row(row)

    def get_user_by_reset_token(self, token_hash: str) -> Optional[User]:
        """Resolve a one-time reset token hash to its user, excluding expired
        rows. Missing and expired tokens both resolve to None so the route
        treats them identically."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT u.id, u.username, u.password_hash, u.salt, u.created_at, u.email"
                " FROM reset_tokens t JOIN users u ON u.id = t.user_id"
                " WHERE t.token_hash = ? AND t.expires_at > ?",
                (token_hash, _utc_now()),
            ).fetchone()
        return _user_from_row(row) if row is not None else None

    def delete_reset_token(self, token_hash: str) -> bool:
        """Consume a one-time reset token; return whether a row was removed."""
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM reset_tokens WHERE token_hash = ?", (token_hash,)
            )
            return cursor.rowcount > 0

    def reset_user_password(
        self,
        user_id: int,
        password_hash: str,
        salt: str,
        token_hash: str,
    ) -> None:
        """Atomic password reset: update the scrypt hash/salt, consume the
        one-time token, and revoke every session for the user — all inside
        one transaction, so a crash cannot leave a usable token or live
        sessions behind a rotated password."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                (password_hash, salt, user_id),
            )
            conn.execute(
                "DELETE FROM reset_tokens WHERE token_hash = ?", (token_hash,)
            )
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    # ---- settings ----

    def get_settings(self, user_id: int) -> AppSettings:
        with self._tx() as conn:
            return self._settings_from_conn(user_id, conn)

    def _settings_from_conn(
        self, user_id: int, conn: sqlite3.Connection
    ) -> AppSettings:
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE user_id = ?", (user_id,)
        ).fetchall()
        stored = {row["key"]: row["value"] for row in rows}
        return AppSettings(
            target_weight=_optional_float(stored.get("target_weight")),
            tip_time=str(stored.get("tip_time", DEFAULT_SETTINGS["tip_time"])),
            reminder_time=str(
                stored.get("reminder_time", DEFAULT_SETTINGS["reminder_time"])
            ),
            reminder_weekday=_optional_int(
                stored.get("reminder_weekday", DEFAULT_SETTINGS["reminder_weekday"])
            ),
            exercise_time=str(
                stored.get("exercise_time", DEFAULT_SETTINGS["exercise_time"])
            ),
            start_weight_override=_optional_float(
                stored.get("start_weight_override")
            ),
            height_cm=_optional_float(stored.get("height_cm")),
        )

    def update_settings(self, user_id: int, updates: dict[str, Any]) -> None:
        with self._tx() as conn:
            for key, value in updates.items():
                if value is None:
                    conn.execute(
                        "DELETE FROM settings WHERE user_id = ? AND key = ?",
                        (user_id, key),
                    )
                else:
                    conn.execute(
                        "INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?)"
                        " ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
                        (user_id, key, str(value)),
                    )
            if any(key in self.REWARD_AFFECTING_KEYS for key in updates):
                self._reconcile_active_rewards(conn, user_id)

    # ---- push subscriptions ----

    def add_subscription(
        self, user_id: int, endpoint: str, p256dh: str, auth: str
    ) -> PushSubscription:
        # endpoint stays globally UNIQUE (one browser = one subscription); a
        # re-subscribe from another user reassigns ownership to the caller.
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(endpoint) DO UPDATE SET"
                " user_id = excluded.user_id, p256dh = excluded.p256dh,"
                " auth = excluded.auth",
                (user_id, endpoint, p256dh, auth),
            )
            row = conn.execute(
                "SELECT id, endpoint, p256dh, auth, created_at"
                " FROM push_subscriptions WHERE endpoint = ?",
                (endpoint,),
            ).fetchone()
        if row is None:
            raise RuntimeError("subscription insert produced no row")
        return _subscription_from_row(row)

    def list_subscriptions(self, user_id: int) -> list[PushSubscription]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, endpoint, p256dh, auth, created_at"
                " FROM push_subscriptions WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        return [_subscription_from_row(row) for row in rows]

    def remove_subscription(self, user_id: int, endpoint: str) -> bool:
        # Ownership check: a user can only remove their own subscription.
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM push_subscriptions WHERE endpoint = ? AND user_id = ?",
                (endpoint, user_id),
            )
            return cursor.rowcount > 0

    # ---- notifications sent (scheduler dedupe) ----

    def is_notification_sent(self, user_id: int, date: str, notif_type: str) -> bool:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT 1 FROM notifications_sent"
                " WHERE user_id = ? AND date = ? AND type = ?",
                (user_id, date, notif_type),
            ).fetchone()
        return row is not None

    def mark_notification_sent(
        self,
        user_id: int,
        date: str,
        notif_type: str,
        sent_at: Optional[str] = None,
    ) -> None:
        # The scheduler passes its own tick's local wall time so persisted
        # sent_at matches the event; direct callers default to a fresh local now.
        with self._tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notifications_sent"
                " (user_id, date, type, sent_at) VALUES (?, ?, ?, ?)",
                (user_id, date, notif_type, sent_at or _local_now()),
            )


async def run_db(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a synchronous Database method on a thread so callers stay async."""
    return await asyncio.to_thread(func, *args, **kwargs)


def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        salt=row["salt"],
        created_at=row["created_at"],
        email=row["email"],
    )


def _reset_token_from_row(row: sqlite3.Row) -> ResetToken:
    return ResetToken(
        id=row["id"],
        user_id=row["user_id"],
        token_hash=row["token_hash"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def _session_from_row(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        user_id=row["user_id"],
        token_hash=row["token_hash"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def _weight_from_row(row: sqlite3.Row) -> WeightEntry:
    return WeightEntry(
        id=row["id"],
        date=row["date"],
        weight_kg=row["weight_kg"],
        created_at=row["created_at"],
    )


def _subscription_from_row(row: sqlite3.Row) -> PushSubscription:
    return PushSubscription(
        id=row["id"],
        endpoint=row["endpoint"],
        p256dh=row["p256dh"],
        auth=row["auth"],
        created_at=row["created_at"],
    )


def _optional_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _local_now() -> str:
    """Host-local wall-clock timestamp for persisted event times."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _utc_now() -> str:
    """UTC wall-clock timestamp for identity rows and session expiry."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
