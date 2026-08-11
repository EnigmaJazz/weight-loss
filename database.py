"""SQLite storage layer: schema, connection handling, row -> dataclass mapping."""

import asyncio
import contextlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional, Sequence

from constants import DEFAULT_SETTINGS, HABIT_TYPES, get_logger
from models import (
    AchievementFacts,
    AchievementQuestFact,
    AppSettings,
    ExerciseDayFacts,
    ExerciseEntry,
    HabitEntry,
    MealEntry,
    MomentumDayFacts,
    MoodEntry,
    PushSubscription,
    Quest,
    QuestDetectionFacts,
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
    # are DISCARDED during migration (maintainer decision) — no backfill.
    """
    CREATE TABLE IF NOT EXISTS weight_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 0,
        date TEXT NOT NULL,
        time TEXT,
        weight_kg REAL NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (user_id, date)
    );
    """,
    # Activity logging: multiple entries per user per date are allowed, so no
    # per-date uniqueness. created_at is always passed explicitly by the insert
    # methods (_local_now()); the DEFAULT is only a schema-level fallback.
    """
    CREATE TABLE IF NOT EXISTS exercise_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        exercise_type TEXT NOT NULL,
        duration_min INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS meal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        calories REAL NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    # Mood and habit logging (r1-quests-xp S3a): multiple entries per user
    # per date are allowed (like exercise/meal), so no per-date uniqueness.
    # Range/allowlist validation (mood 1-5, HABIT_TYPES) lives in routes.py,
    # matching the exercise/meal template.
    """
    CREATE TABLE IF NOT EXISTS mood_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        mood INTEGER NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS habit_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        time TEXT,
        habit_type TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
    # Daily quests (r1-quests-xp): per-user rows with NO per-date uniqueness —
    # a replacement adds a row, and another user MAY hold the same key+date.
    # Status transitions are validated in quests.py, not by the schema.
    """
    CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        quest_key TEXT NOT NULL,
        domain TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        xp_value INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open'
            CHECK (status IN ('open', 'done', 'skipped', 'replaced')),
        difficulty TEXT NOT NULL,
        source TEXT NOT NULL,
        completed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
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


class DuplicateDateError(Exception):
    """Raised when update_entry moves an entry onto a date that already has
    another entry for the same user (one entry per user per date)."""


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
            self._migrate_activity_time(conn)

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

    def _migrate_activity_time(self, conn: sqlite3.Connection) -> None:
        """Add the nullable activity ``time`` column to databases created before
        time-of-day support. Idempotent: fresh schemas already carry it, so each
        ALTER runs at most once. Runs inside the caller's transaction."""
        for table in ("weight_entries", "exercise_entries", "meal_entries"):
            columns = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if "time" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN time TEXT")

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
                "SELECT id, date, time, weight_kg, created_at"
                " FROM weight_entries WHERE user_id = ? ORDER BY date DESC",
                (user_id,),
            ).fetchall()
        return [_weight_from_row(row) for row in rows]

    def get_entry_by_date(self, user_id: int, date: str) -> Optional[WeightEntry]:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id, date, time, weight_kg, created_at"
                " FROM weight_entries WHERE user_id = ? AND date = ?",
                (user_id, date),
            ).fetchone()
        return _weight_from_row(row) if row is not None else None

    def upsert_entry(
        self, user_id: int, date: str, weight_kg: float, time: Optional[str] = None
    ) -> WeightEntry:
        with self._tx() as conn:
            entry = self._upsert_entry_conn(conn, user_id, date, weight_kg, time)
            self._reconcile_active_rewards(conn, user_id)
        return entry

    def _upsert_entry_conn(
        self,
        conn: sqlite3.Connection,
        user_id: int,
        date: str,
        weight_kg: float,
        time: Optional[str],
    ) -> WeightEntry:
        """Insert-or-update one weight row using the caller's transaction; the
        UNIQUE(user_id, date) constraint makes re-POSTing the same date
        idempotent. Shared by upsert_entry and complete_onboarding."""
        conn.execute(
            "INSERT INTO weight_entries (user_id, date, time, weight_kg, created_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(user_id, date) DO UPDATE SET"
            " weight_kg = excluded.weight_kg, time = excluded.time",
            (user_id, date, time, weight_kg, _local_now()),
        )
        row = conn.execute(
            "SELECT id, date, time, weight_kg, created_at"
            " FROM weight_entries WHERE user_id = ? AND date = ?",
            (user_id, date),
        ).fetchone()
        if row is None:
            raise RuntimeError("upsert produced no row")
        return _weight_from_row(row)

    def update_entry(
        self,
        user_id: int,
        entry_id: int,
        date: str,
        weight_kg: float,
        time: Optional[str] = None,
    ) -> Optional[WeightEntry]:
        # Ownership is checked first so a cross-user id surfaces as 404 even
        # when the new date is taken by the caller's own entries (no info
        # leak); the date-conflict check runs second so moving onto another
        # entry's date raises instead of silently overwriting that day. The
        # UNIQUE(user_id, date) constraint backs both checks atomically.
        with self._tx() as conn:
            owned = conn.execute(
                "SELECT id FROM weight_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            ).fetchone()
            if owned is None:
                return None
            conflict = conn.execute(
                "SELECT id FROM weight_entries"
                " WHERE user_id = ? AND date = ? AND id != ?",
                (user_id, date, entry_id),
            ).fetchone()
            if conflict is not None:
                raise DuplicateDateError(date)
            conn.execute(
                "UPDATE weight_entries SET date = ?, weight_kg = ?, time = ?"
                " WHERE id = ? AND user_id = ?",
                (date, weight_kg, time, entry_id, user_id),
            )
            row = conn.execute(
                "SELECT id, date, time, weight_kg, created_at"
                " FROM weight_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            ).fetchone()
            self._reconcile_active_rewards(conn, user_id)
        if row is None:
            raise RuntimeError("update produced no row")
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

    # ---- exercise entries (activity logging) ----

    def list_exercise(self, user_id: int) -> list[ExerciseEntry]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, time, exercise_type, duration_min, created_at"
                " FROM exercise_entries WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [_exercise_from_row(row) for row in rows]

    def insert_exercise(
        self,
        user_id: int,
        date: str,
        exercise_type: str,
        duration_min: int,
        time: Optional[str] = None,
    ) -> ExerciseEntry:
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO exercise_entries"
                " (user_id, date, time, exercise_type, duration_min, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, date, time, exercise_type, duration_min, _local_now()),
            )
            row = conn.execute(
                "SELECT id, date, time, exercise_type, duration_min, created_at"
                " FROM exercise_entries WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("exercise insert produced no row")
        return _exercise_from_row(row)

    def delete_exercise(self, user_id: int, entry_id: int) -> bool:
        # Ownership check inside the DELETE: a cross-user id deletes nothing.
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM exercise_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            )
            return cursor.rowcount > 0

    def update_exercise(
        self,
        user_id: int,
        entry_id: int,
        date: str,
        time: Optional[str],
        exercise_type: str,
        duration_min: int,
    ) -> Optional[ExerciseEntry]:
        # Ownership check inside the UPDATE: a cross-user id updates nothing.
        with self._tx() as conn:
            conn.execute(
                "UPDATE exercise_entries"
                " SET date = ?, time = ?, exercise_type = ?, duration_min = ?"
                " WHERE id = ? AND user_id = ?",
                (date, time, exercise_type, duration_min, entry_id, user_id),
            )
            row = conn.execute(
                "SELECT id, date, time, exercise_type, duration_min, created_at"
                " FROM exercise_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return _exercise_from_row(row)

    # ---- meal entries (activity logging) ----

    def list_meals(self, user_id: int) -> list[MealEntry]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, time, calories, created_at"
                " FROM meal_entries WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [_meal_from_row(row) for row in rows]

    def insert_meal(
        self, user_id: int, date: str, calories: float, time: Optional[str] = None
    ) -> MealEntry:
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO meal_entries (user_id, date, time, calories, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_id, date, time, calories, _local_now()),
            )
            row = conn.execute(
                "SELECT id, date, time, calories, created_at"
                " FROM meal_entries WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("meal insert produced no row")
        return _meal_from_row(row)

    def delete_meal(self, user_id: int, entry_id: int) -> bool:
        # Ownership check inside the DELETE: a cross-user id deletes nothing.
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM meal_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            )
            return cursor.rowcount > 0

    def update_meal(
        self,
        user_id: int,
        entry_id: int,
        date: str,
        time: Optional[str],
        calories: float,
    ) -> Optional[MealEntry]:
        # Ownership check inside the UPDATE: a cross-user id updates nothing.
        with self._tx() as conn:
            conn.execute(
                "UPDATE meal_entries"
                " SET date = ?, time = ?, calories = ?"
                " WHERE id = ? AND user_id = ?",
                (date, time, calories, entry_id, user_id),
            )
            row = conn.execute(
                "SELECT id, date, time, calories, created_at"
                " FROM meal_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return _meal_from_row(row)

    # ---- mood entries (r1-quests-xp S3a) ----

    def list_mood_entries(self, user_id: int) -> list[MoodEntry]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, time, mood, note, created_at"
                " FROM mood_entries WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [_mood_from_row(row) for row in rows]

    def insert_mood_entry(
        self,
        user_id: int,
        date: str,
        mood: int,
        note: Optional[str],
        time: Optional[str] = None,
    ) -> MoodEntry:
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO mood_entries"
                " (user_id, date, time, mood, note, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, date, time, mood, note, _local_now()),
            )
            row = conn.execute(
                "SELECT id, date, time, mood, note, created_at"
                " FROM mood_entries WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("mood insert produced no row")
        return _mood_from_row(row)

    def delete_mood_entry(self, user_id: int, entry_id: int) -> bool:
        # Ownership check inside the DELETE: a cross-user id deletes nothing.
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM mood_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            )
            return cursor.rowcount > 0

    # ---- habit entries (r1-quests-xp S3a) ----

    def list_habit_entries(self, user_id: int) -> list[HabitEntry]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, time, habit_type, created_at"
                " FROM habit_entries WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [_habit_from_row(row) for row in rows]

    def insert_habit_entry(
        self,
        user_id: int,
        date: str,
        habit_type: str,
        time: Optional[str] = None,
    ) -> HabitEntry:
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO habit_entries"
                " (user_id, date, time, habit_type, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_id, date, time, habit_type, _local_now()),
            )
            row = conn.execute(
                "SELECT id, date, time, habit_type, created_at"
                " FROM habit_entries WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("habit insert produced no row")
        return _habit_from_row(row)

    def delete_habit_entry(self, user_id: int, entry_id: int) -> bool:
        # Ownership check inside the DELETE: a cross-user id deletes nothing.
        with self._tx() as conn:
            cursor = conn.execute(
                "DELETE FROM habit_entries WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            )
            return cursor.rowcount > 0

    # ---- active reward checkpoints ----

    REWARD_AFFECTING_KEYS: tuple[str, ...] = (
        "target_weight",
        "start_weight_override",
        "target_bmi",  # moves the resolved target in BMI mode
        "height_cm",  # moves the BMI-derived target in BMI mode
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
            "SELECT id, date, time, weight_kg, created_at FROM weight_entries"
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
            target_bmi=_optional_float(stored.get("target_bmi")),
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
            # Plain strings: the settings table is key/value with no schema
            # columns, so defaults cover rows that predate these keys.
            weight_unit=str(
                stored.get("weight_unit", DEFAULT_SETTINGS["weight_unit"])
            ),
            height_unit=str(
                stored.get("height_unit", DEFAULT_SETTINGS["height_unit"])
            ),
            target_unit=str(
                stored.get("target_unit", DEFAULT_SETTINGS["target_unit"])
            ),
            weight_display=str(
                stored.get("weight_display", DEFAULT_SETTINGS["weight_display"])
            ),
            theme=str(stored.get("theme", DEFAULT_SETTINGS["theme"])),
            onboarding_complete=_optional_bool(stored.get("onboarding_complete")),
            # Goals & lifestyle (user-onboarding): nullable strings default to
            # None; JSON lists default to [] and round-trip with order intact.
            primary_goal=_optional_str(stored.get("primary_goal")),
            secondary_goals=_optional_json_list(stored.get("secondary_goals")),
            health_domains=_optional_json_list(stored.get("health_domains")),
            activity_level=_optional_str(stored.get("activity_level")),
        )

    def _apply_settings(
        self, conn: sqlite3.Connection, user_id: int, updates: dict[str, Any]
    ) -> None:
        """Persist one settings update batch using the caller's transaction.
        None deletes the row (restore default); anything else upserts the
        string form. Shared by update_settings and complete_onboarding."""
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
                    (user_id, key, _settings_value(value)),
                )

    def update_settings(self, user_id: int, updates: dict[str, Any]) -> None:
        with self._tx() as conn:
            self._apply_settings(conn, user_id, updates)
            if any(key in self.REWARD_AFFECTING_KEYS for key in updates):
                self._reconcile_active_rewards(conn, user_id)

    def complete_onboarding(
        self, user_id: int, payload: dict[str, Any]
    ) -> None:
        """Atomic wizard completion: settings, today's first weight entry, and
        reward reconciliation in one transaction.

        ``payload`` is the validated OnboardingIn dump: height, one target,
        unit/schedule preferences, and the first weight. The flag is written
        inside the same transaction as everything else, so a mid-transaction
        failure leaves no settings, weight, or reward change behind, and a
        re-POST (same or updated prefs) overwrites rather than appends.
        """
        with self._tx() as conn:
            updates: dict[str, Any] = dict(payload)
            updates.pop("weight_kg", None)
            updates["onboarding_complete"] = "True"
            # AD2: exactly one of target_weight/target_bmi is present (the
            # OnboardingIn XOR); null the other so a mode switch on a later
            # POST cannot leave two persisted targets (same rule as put_settings).
            if updates.get("target_weight") is not None:
                updates["target_bmi"] = None
            elif updates.get("target_bmi") is not None:
                updates["target_weight"] = None
            self._apply_settings(conn, user_id, updates)
            self._upsert_entry_conn(
                conn, user_id, _today(), float(payload["weight_kg"]), None
            )
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


    # ---- daily quests (r1-quests-xp) ----

    def insert_quests(
        self, user_id: int, date_str: str, drafts: Sequence[Quest]
    ) -> list[Quest]:
        """Persist any of ``drafts`` not already assigned to the user+date
        (idempotent — regenerating the same day adds nothing) and return every
        row for the day in insertion order. Replacement passes the single
        eligible draft; already-assigned keys are skipped."""
        with self._tx() as conn:
            existing = {
                row["quest_key"]
                for row in conn.execute(
                    "SELECT quest_key FROM quests WHERE user_id = ? AND date = ?",
                    (user_id, date_str),
                ).fetchall()
            }
            for draft in drafts:
                if draft.quest_key in existing:
                    continue
                conn.execute(
                    "INSERT INTO quests"
                    " (user_id, date, quest_key, domain, title, description,"
                    "  xp_value, status, difficulty, source, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        date_str,
                        draft.quest_key,
                        draft.domain,
                        draft.title,
                        draft.description,
                        draft.xp_value,
                        draft.status,
                        draft.difficulty,
                        draft.source,
                        _local_now(),
                    ),
                )
                existing.add(draft.quest_key)
            rows = conn.execute(
                "SELECT id, date, quest_key, domain, title, description, xp_value,"
                " status, difficulty, source, completed_at, created_at"
                " FROM quests WHERE user_id = ? AND date = ? ORDER BY id",
                (user_id, date_str),
            ).fetchall()
        return [_quest_from_row(row) for row in rows]

    def list_quests_for_date(self, user_id: int, date_str: str) -> list[Quest]:
        """All quest rows for one user+date, oldest first (insertion order)."""
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, quest_key, domain, title, description, xp_value,"
                " status, difficulty, source, completed_at, created_at"
                " FROM quests WHERE user_id = ? AND date = ? ORDER BY id",
                (user_id, date_str),
            ).fetchall()
        return [_quest_from_row(row) for row in rows]

    def get_quest(self, user_id: int, quest_id: int) -> Optional[Quest]:
        """Ownership-scoped single-row read; None for a foreign/missing id (404
        at the API — the same concealment as update_quest_status)."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id, date, quest_key, domain, title, description, xp_value,"
                " status, difficulty, source, completed_at, created_at"
                " FROM quests WHERE id = ? AND user_id = ?",
                (quest_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return _quest_from_row(row)

    def list_quest_history(
        self, user_id: int, before_date: str, limit: int = 10
    ) -> list[Quest]:
        """Newest quest rows strictly before ``before_date`` (past days' history),
        newest date first, capped at ``limit`` — the bounded history the GET
        endpoint returns alongside today's current rows."""
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, quest_key, domain, title, description, xp_value,"
                " status, difficulty, source, completed_at, created_at"
                " FROM quests WHERE user_id = ? AND date < ?"
                " ORDER BY date DESC, id DESC LIMIT ?",
                (user_id, before_date, limit),
            ).fetchall()
        return [_quest_from_row(row) for row in rows]

    def update_quest_status(
        self,
        user_id: int,
        quest_id: int,
        status: str,
        source: str = "manual",
    ) -> Optional[Quest]:
        """Ownership-scoped status write; returns the updated quest, or None
        for a foreign/missing id (404 at the API). completed_at is stamped
        with the local wall clock when the quest becomes done and cleared
        otherwise. Transition rules live in quests.py — this method persists a
        decided transition."""
        completed_at = _local_now() if status == "done" else None
        with self._tx() as conn:
            conn.execute(
                "UPDATE quests SET status = ?, source = ?, completed_at = ?"
                " WHERE id = ? AND user_id = ?",
                (status, source, completed_at, quest_id, user_id),
            )
            row = conn.execute(
                "SELECT id, date, quest_key, domain, title, description, xp_value,"
                " status, difficulty, source, completed_at, created_at"
                " FROM quests WHERE id = ? AND user_id = ?",
                (quest_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return _quest_from_row(row)

    def list_assigned_keys_today(self, user_id: int, date_str: str) -> set[str]:
        """Distinct quest keys with any row for the user+date (assigned or
        replaced) — the replacement-exclusion set."""
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT DISTINCT quest_key FROM quests"
                " WHERE user_id = ? AND date = ?",
                (user_id, date_str),
            ).fetchall()
        return {row["quest_key"] for row in rows}

    def count_replaced_today(self, user_id: int, date_str: str) -> int:
        """Replacement rows for the user+date; the one-per-day cap checks
        this before allowing another replace."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM quests"
                " WHERE user_id = ? AND date = ? AND status = 'replaced'",
                (user_id, date_str),
            ).fetchone()
        return int(row["n"])

    def quest_detection_facts(self, user_id: int, date_str: str) -> QuestDetectionFacts:
        """Detection facts for one user+date gathered from the weight,
        exercise, meal, mood, and habit tables. The habit presence is
        HABIT_TYPES-driven: only rows whose habit_type is in the catalogue
        qualify, so a catalogue change propagates here without touching
        quests.py. has_any_entry covers every qualifying row source."""
        habit_placeholders = ",".join("?" for _ in HABIT_TYPES)
        with self._tx() as conn:
            weight = conn.execute(
                "SELECT 1 FROM weight_entries WHERE user_id = ? AND date = ? LIMIT 1",
                (user_id, date_str),
            ).fetchone()
            exercise = conn.execute(
                "SELECT COALESCE(SUM(duration_min), 0) AS total, COUNT(*) AS n"
                " FROM exercise_entries WHERE user_id = ? AND date = ?",
                (user_id, date_str),
            ).fetchone()
            meal = conn.execute(
                "SELECT 1 FROM meal_entries WHERE user_id = ? AND date = ? LIMIT 1",
                (user_id, date_str),
            ).fetchone()
            mood = conn.execute(
                "SELECT 1 FROM mood_entries WHERE user_id = ? AND date = ? LIMIT 1",
                (user_id, date_str),
            ).fetchone()
            habit = conn.execute(
                f"SELECT 1 FROM habit_entries WHERE user_id = ? AND date = ?"
                f" AND habit_type IN ({habit_placeholders}) LIMIT 1",
                (user_id, date_str, *HABIT_TYPES),
            ).fetchone()
        return QuestDetectionFacts(
            date=date_str,
            has_weight=weight is not None,
            exercise_min=int(exercise["total"]),
            has_meal=meal is not None,
            has_mood=mood is not None,
            has_habit=habit is not None,
            has_any_entry=(
                weight is not None
                or int(exercise["n"]) > 0
                or meal is not None
                or mood is not None
                or habit is not None
            ),
        )

    def total_xp_for_user(self, user_id: int) -> int:
        """Derived XP: the SUM of xp_value across the user's done quests.
        Open, skipped, and replaced quests contribute zero; no ledger is ever
        written (reward_events is dropped on every schema init)."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(xp_value), 0) AS total FROM quests"
                " WHERE user_id = ? AND status = 'done'",
                (user_id,),
            ).fetchone()
        return int(row["total"])

    def list_recent_done_quests(
        self, user_id: int, limit: int = 10
    ) -> list[Quest]:
        """Newest done quests for the user, newest date first, capped at
        ``limit`` — the recent-completions list on GET /api/xp. Quests can
        only be completed on their own date, so date order is completion
        order; id DESC breaks same-day ties."""
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, date, quest_key, domain, title, description, xp_value,"
                " status, difficulty, source, completed_at, created_at"
                " FROM quests WHERE user_id = ? AND status = 'done'"
                " ORDER BY date DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [_quest_from_row(row) for row in rows]

    def momentum_facts(
        self, user_id: int, start: str, end: str
    ) -> list[MomentumDayFacts]:
        """Per-date momentum facts for one user across [start, end] inclusive:
        current assigned quests (replaced rows are not assignments), done
        quests, and log-row counts from the weight/exercise/meal/mood/habit
        tables."""
        with self._tx() as conn:
            quest_rows, log_rows = _momentum_day_rows(conn, user_id, start, end)
        facts: dict[str, MomentumDayFacts] = {}
        for row in quest_rows:
            facts[row["date"]] = MomentumDayFacts(
                date=row["date"],
                assigned_quests=int(row["assigned"]),
                done_quests=int(row["done_n"]),
            )
        for row in log_rows:
            day = row["date"]
            day_facts = facts.get(day)
            if day_facts is None:
                day_facts = MomentumDayFacts(date=day)
                facts[day] = day_facts
            day_facts.log_rows += int(row["n"])
        return sorted(facts.values(), key=lambda fact: fact.date)

    def achievement_facts(self, user_id: int) -> AchievementFacts:
        """One ownership-scoped snapshot for the achievements engine: done
        quest rows (date/quest_key/domain), per-date momentum facts across all
        history (same shape as momentum_facts), and per-date summed exercise
        minutes. Every read filters on ``WHERE user_id = ?`` inside one
        transaction, so cross-user rows can never leak into the snapshot."""
        with self._tx() as conn:
            done_rows = conn.execute(
                "SELECT date, quest_key, domain FROM quests"
                " WHERE user_id = ? AND status = 'done' ORDER BY date, id",
                (user_id,),
            ).fetchall()
            quest_rows, log_rows = _momentum_day_rows(conn, user_id)
            exercise_rows = conn.execute(
                "SELECT date, SUM(duration_min) AS duration_min"
                " FROM exercise_entries WHERE user_id = ? GROUP BY date",
                (user_id,),
            ).fetchall()
        done_quests = [
            AchievementQuestFact(
                date=row["date"], quest_key=row["quest_key"], domain=row["domain"]
            )
            for row in done_rows
        ]
        by_date: dict[str, MomentumDayFacts] = {}
        for row in quest_rows:
            by_date[row["date"]] = MomentumDayFacts(
                date=row["date"],
                assigned_quests=int(row["assigned"]),
                done_quests=int(row["done_n"]),
            )
        for row in log_rows:
            day = row["date"]
            day_facts = by_date.get(day)
            if day_facts is None:
                day_facts = MomentumDayFacts(date=day)
                by_date[day] = day_facts
            day_facts.log_rows += int(row["n"])
        exercise_days = [
            ExerciseDayFacts(date=row["date"], duration_min=int(row["duration_min"]))
            for row in exercise_rows
        ]
        return AchievementFacts(
            done_quests=done_quests,
            momentum_days=sorted(by_date.values(), key=lambda fact: fact.date),
            exercise_days=sorted(exercise_days, key=lambda entry: entry.date),
        )


def _momentum_day_rows(
    conn: sqlite3.Connection,
    user_id: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """Quest and log-table day-row counts for one user, optionally bounded to
    [start, end] inclusive (shared by momentum_facts and achievement_facts).
    Returns ``(quest_rows, log_rows)``: quest rows carry ``assigned`` and
    ``done_n``; log rows carry ``n``. Callers merge both into
    MomentumDayFacts."""
    bounds = ""
    params: tuple[Any, ...] = (user_id,)
    if start is not None and end is not None:
        bounds = " AND date BETWEEN ? AND ?"
        params = (user_id, start, end)
    quest_rows = conn.execute(
        "SELECT date,"
        " SUM(CASE WHEN status != 'replaced' THEN 1 ELSE 0 END)"
        "   AS assigned,"
        " SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done_n"
        f" FROM quests WHERE user_id = ?{bounds} GROUP BY date",
        params,
    ).fetchall()
    log_rows: list[sqlite3.Row] = []
    for table in (
        "weight_entries",
        "exercise_entries",
        "meal_entries",
        "mood_entries",
        "habit_entries",
    ):
        log_rows.extend(
            conn.execute(
                f"SELECT date, COUNT(*) AS n FROM {table}"
                f" WHERE user_id = ?{bounds} GROUP BY date",
                params,
            ).fetchall()
        )
    return quest_rows, log_rows


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
        time=row["time"],
    )


def _exercise_from_row(row: sqlite3.Row) -> ExerciseEntry:
    return ExerciseEntry(
        id=row["id"],
        date=row["date"],
        time=row["time"],
        exercise_type=row["exercise_type"],
        duration_min=row["duration_min"],
        created_at=row["created_at"],
    )


def _meal_from_row(row: sqlite3.Row) -> MealEntry:
    return MealEntry(
        id=row["id"],
        date=row["date"],
        time=row["time"],
        calories=row["calories"],
        created_at=row["created_at"],
    )


def _mood_from_row(row: sqlite3.Row) -> MoodEntry:
    return MoodEntry(
        id=row["id"],
        date=row["date"],
        time=row["time"],
        mood=row["mood"],
        note=row["note"],
        created_at=row["created_at"],
    )


def _habit_from_row(row: sqlite3.Row) -> HabitEntry:
    return HabitEntry(
        id=row["id"],
        date=row["date"],
        time=row["time"],
        habit_type=row["habit_type"],
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


def _quest_from_row(row: sqlite3.Row) -> Quest:
    return Quest(
        id=row["id"],
        date=row["date"],
        quest_key=row["quest_key"],
        domain=row["domain"],
        title=row["title"],
        description=row["description"],
        xp_value=row["xp_value"],
        status=row["status"],
        difficulty=row["difficulty"],
        source=row["source"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


def _optional_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _optional_str(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    return value


def _optional_json_list(value: Optional[str]) -> list[str]:
    """Parse a settings k/v JSON-list value; absent/empty -> [] and a
    malformed value degrades to [] so a legacy row can never break reads."""
    if value is None or value == "":
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _settings_value(value: Any) -> str:
    """Settings k/v string form: JSON for list values so they round-trip with
    order intact; plain str for everything else (bools/floats keep the form
    the existing readers already parse)."""
    if isinstance(value, list):
        return json.dumps(value)
    return str(value)


def _optional_bool(value: Optional[str]) -> bool:
    """Parse the settings k/v boolean representation; absent/empty -> False."""
    if value is None or value == "":
        return False
    return value.strip().lower() == "true"


def _local_now() -> str:
    """Host-local wall-clock timestamp for persisted event times."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    """Host-local today's date (YYYY-MM-DD) for "today's entry" semantics."""
    return datetime.now().strftime("%Y-%m-%d")


def _utc_now() -> str:
    """UTC wall-clock timestamp for identity rows and session expiry."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
