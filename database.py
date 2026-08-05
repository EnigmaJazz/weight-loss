"""SQLite storage layer: schema, connection handling, row -> dataclass mapping."""

import asyncio
import contextlib
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

from constants import DEFAULT_SETTINGS, get_logger
from models import AppSettings, PushSubscription, Session, User, WeightEntry
from rewards import reward_state

logger = get_logger("database")

# One statement per element: init_schema runs each inside the explicit
# transaction (BEGIN) instead of executescript, which would implicitly COMMIT
# the open transaction and break the all-or-nothing boundary.
SCHEMA_STATEMENTS: tuple[str, ...] = (
    "DROP TABLE IF EXISTS reward_events;",
    """
    CREATE TABLE IF NOT EXISTS weight_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        weight_kg REAL NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS push_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT NOT NULL UNIQUE,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS active_rewards (
        checkpoint_percent INTEGER PRIMARY KEY,
        threshold_kg REAL NOT NULL,
        earned_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS notifications_sent (
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (date, type)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
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
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
)


class DuplicateUsernameError(Exception):
    """Raised when create_user hits the username UNIQUE constraint."""


class Database:
    """Thin wrapper around one SQLite connection, serialized by a lock.

    Lives on ``app.state.db``. All methods are synchronous; callers on the
    request path must wrap them with :func:`run_db` to stay async.
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

    # ---- weight entries ----

    def list_entries(self) -> list[WeightEntry]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, weight_kg, created_at"
                " FROM weight_entries ORDER BY date DESC"
            ).fetchall()
        return [_weight_from_row(row) for row in rows]

    def get_entry_by_date(self, date: str) -> Optional[WeightEntry]:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id, date, weight_kg, created_at"
                " FROM weight_entries WHERE date = ?",
                (date,),
            ).fetchone()
        return _weight_from_row(row) if row is not None else None

    def upsert_entry(self, date: str, weight_kg: float) -> WeightEntry:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO weight_entries (date, weight_kg, created_at)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(date) DO UPDATE SET weight_kg = excluded.weight_kg",
                (date, weight_kg, _local_now()),
            )
            row = conn.execute(
                "SELECT id, date, weight_kg, created_at"
                " FROM weight_entries WHERE date = ?",
                (date,),
            ).fetchone()
            self._reconcile_active_rewards(conn)
        if row is None:
            raise RuntimeError("upsert produced no row")
        return _weight_from_row(row)

    def delete_entry(self, entry_id: int) -> bool:
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM weight_entries WHERE id = ?", (entry_id,)
            )
            deleted = cursor.rowcount > 0
            self._reconcile_active_rewards(conn)
            return deleted

    # ---- active reward checkpoints ----

    REWARD_AFFECTING_KEYS: tuple[str, ...] = (
        "target_weight",
        "start_weight_override",
    )

    def reconcile_active_rewards(self) -> None:
        """Reconcile the persisted checkpoint set in its own transaction
        (startup entry point after the schema is created)."""
        with self._tx() as conn:
            self._reconcile_active_rewards(conn)

    def list_active_rewards(self) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT checkpoint_percent, threshold_kg, earned_at"
                " FROM active_rewards ORDER BY checkpoint_percent"
            ).fetchall()
        return [dict(row) for row in rows]

    def _reconcile_active_rewards(self, conn: sqlite3.Connection) -> None:
        """Transactional core: sync active_rewards to the derived checkpoint
        state using the caller's open transaction. Earned timestamps survive
        while a checkpoint stays active; revoked rows are removed and re-earned
        ones get a fresh local timestamp."""
        entry_rows = conn.execute(
            "SELECT id, date, weight_kg, created_at FROM weight_entries"
        ).fetchall()
        entries = [_weight_from_row(row) for row in entry_rows]
        state = reward_state(entries, self._settings_from_conn(conn))
        existing = {
            row["checkpoint_percent"]
            for row in conn.execute(
                "SELECT checkpoint_percent FROM active_rewards"
            ).fetchall()
        }
        derived = {cp.percent for cp in state.active}
        for percent in existing - derived:
            conn.execute(
                "DELETE FROM active_rewards WHERE checkpoint_percent = ?",
                (percent,),
            )
        for cp in state.active:
            conn.execute(
                "INSERT INTO active_rewards"
                " (checkpoint_percent, threshold_kg, earned_at)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(checkpoint_percent) DO UPDATE SET"
                " threshold_kg = excluded.threshold_kg",
                (cp.percent, cp.threshold_kg, _local_now()),
            )

    # ---- identity: users ----

    def create_user(self, username: str, password_hash: str, salt: str) -> User:
        """Insert a user; raise DuplicateUsernameError on a taken username."""
        with self._tx() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, salt, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (username, password_hash, salt, _utc_now()),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateUsernameError(username) from exc
            row = conn.execute(
                "SELECT id, username, password_hash, salt, created_at"
                " FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("user insert produced no row")
        return _user_from_row(row)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Fetch a user by its stored (lowercased) username."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, salt, created_at"
                " FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return _user_from_row(row) if row is not None else None

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
                "SELECT u.id, u.username, u.password_hash, u.salt, u.created_at"
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

    def delete_expired_sessions(self, now: str) -> int:
        """Sweep sessions expired by the given UTC cutoff; return the count."""
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE expires_at <= ?", (now,)
            )
            return cursor.rowcount

    # ---- settings ----

    def get_settings(self) -> AppSettings:
        with self._tx() as conn:
            return self._settings_from_conn(conn)

    def _settings_from_conn(self, conn: sqlite3.Connection) -> AppSettings:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
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

    def update_settings(self, updates: dict[str, Any]) -> None:
        with self._tx() as conn:
            for key, value in updates.items():
                if value is None:
                    conn.execute(
                        "DELETE FROM settings WHERE key = ?", (key,)
                    )
                else:
                    conn.execute(
                        "INSERT INTO settings (key, value) VALUES (?, ?)"
                        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, str(value)),
                    )
            if any(key in self.REWARD_AFFECTING_KEYS for key in updates):
                self._reconcile_active_rewards(conn)

    # ---- push subscriptions ----

    def add_subscription(
        self, endpoint: str, p256dh: str, auth: str
    ) -> PushSubscription:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO push_subscriptions (endpoint, p256dh, auth)"
                " VALUES (?, ?, ?)"
                " ON CONFLICT(endpoint) DO UPDATE SET"
                " p256dh = excluded.p256dh, auth = excluded.auth",
                (endpoint, p256dh, auth),
            )
            row = conn.execute(
                "SELECT id, endpoint, p256dh, auth, created_at"
                " FROM push_subscriptions WHERE endpoint = ?",
                (endpoint,),
            ).fetchone()
        if row is None:
            raise RuntimeError("subscription insert produced no row")
        return _subscription_from_row(row)

    def list_subscriptions(self) -> list[PushSubscription]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, endpoint, p256dh, auth, created_at"
                " FROM push_subscriptions ORDER BY id"
            ).fetchall()
        return [_subscription_from_row(row) for row in rows]

    def remove_subscription(self, endpoint: str) -> bool:
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,)
            )
            return cursor.rowcount > 0

    # ---- notifications sent (scheduler dedupe) ----

    def is_notification_sent(self, date: str, notif_type: str) -> bool:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT 1 FROM notifications_sent WHERE date = ? AND type = ?",
                (date, notif_type),
            ).fetchone()
        return row is not None

    def mark_notification_sent(
        self, date: str, notif_type: str, sent_at: Optional[str] = None
    ) -> None:
        # The scheduler passes its own tick's local wall time so persisted
        # sent_at matches the event; direct callers default to a fresh local now.
        with self._tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notifications_sent (date, type, sent_at)"
                " VALUES (?, ?, ?)",
                (date, notif_type, sent_at or _local_now()),
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
