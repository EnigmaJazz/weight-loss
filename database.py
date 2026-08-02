"""SQLite storage layer: schema, connection handling, row -> dataclass mapping."""

import asyncio
import contextlib
import sqlite3
import threading
from typing import Any, Callable, Iterator, Optional

from constants import DEFAULT_SETTINGS, get_logger
from models import AppSettings, PushSubscription, WeightEntry
from rewards import milestone_levels

logger = get_logger("database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS weight_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    weight_kg REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reward_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone_kg REAL NOT NULL UNIQUE,
    earned_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications_sent (
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (date, type)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    """Thin wrapper around one SQLite connection, serialized by a lock.

    Lives on ``app.state.db``. All methods are synchronous; callers on the
    request path must wrap them with :func:`run_db` to stay async.
    """

    def __init__(self, db_path: str) -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None
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
            conn.executescript(SCHEMA)

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
                "INSERT INTO weight_entries (date, weight_kg) VALUES (?, ?)"
                " ON CONFLICT(date) DO UPDATE SET weight_kg = excluded.weight_kg",
                (date, weight_kg),
            )
            row = conn.execute(
                "SELECT id, date, weight_kg, created_at"
                " FROM weight_entries WHERE date = ?",
                (date,),
            ).fetchone()
        if row is None:
            raise RuntimeError("upsert produced no row")
        return _weight_from_row(row)

    def delete_entry(self, entry_id: int) -> bool:
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM weight_entries WHERE id = ?", (entry_id,)
            )
            return cursor.rowcount > 0

    # ---- reward events ----

    def reconcile_milestones(
        self, baseline: float, current: float, step: float
    ) -> list[float]:
        """Insert any newly-earned milestone levels, returning the new ones."""
        lost = baseline - current
        levels = milestone_levels(lost, step)
        new_levels: list[float] = []
        if not levels:
            return new_levels
        with self._tx() as conn:
            earned_rows = conn.execute(
                "SELECT milestone_kg FROM reward_events"
            ).fetchall()
            earned = {row["milestone_kg"] for row in earned_rows}
            for level in levels:
                if level not in earned:
                    conn.execute(
                        "INSERT OR IGNORE INTO reward_events (milestone_kg)"
                        " VALUES (?)",
                        (level,),
                    )
                    new_levels.append(level)
        return new_levels

    def list_milestone_rows(self) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT milestone_kg, earned_at FROM reward_events"
                " ORDER BY milestone_kg"
            ).fetchall()
        return [dict(row) for row in rows]

    # ---- settings ----

    def get_settings(self) -> AppSettings:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT key, value FROM settings"
            ).fetchall()
        stored = {row["key"]: row["value"] for row in rows}
        return AppSettings(
            target_weight=_optional_float(stored.get("target_weight")),
            milestone_step_kg=_float(
                stored.get(
                    "milestone_step_kg", DEFAULT_SETTINGS["milestone_step_kg"]
                )
            ),
            tip_time=str(stored.get("tip_time", DEFAULT_SETTINGS["tip_time"])),
            reminder_time=str(
                stored.get("reminder_time", DEFAULT_SETTINGS["reminder_time"])
            ),
            exercise_time=str(
                stored.get("exercise_time", DEFAULT_SETTINGS["exercise_time"])
            ),
            start_weight_override=_optional_float(
                stored.get("start_weight_override")
            ),
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

    def mark_notification_sent(self, date: str, notif_type: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notifications_sent (date, type)"
                " VALUES (?, ?)",
                (date, notif_type),
            )


async def run_db(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a synchronous Database method on a thread so callers stay async."""
    return await asyncio.to_thread(func, *args, **kwargs)


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


def _float(value: object) -> float:
    return float(str(value))
