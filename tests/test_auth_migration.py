"""Legacy single-user DB migration: user_id columns and transactional table
rebuilds.

Seeds a database with the pre-auth schema (no user_id anywhere), boots the app
so init_schema migrates it, and verifies the legacy rows are DISCARDED — every
new account starts fresh and sets its own target/height/schedules (the old
pre-auth rows were smoke-test artifacts, not real per-user data).
"""

import httpx
import pytest

from database import Database
from main import create_app, init_app_state

# The five pre-auth table definitions, exactly as they existed before
# user-accounts-auth (single-user, no user_id, global UNIQUE/PK constraints).
LEGACY_DDL: tuple[str, ...] = (
    """
    CREATE TABLE weight_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        weight_kg REAL NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE push_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT NOT NULL UNIQUE,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE active_rewards (
        checkpoint_percent INTEGER PRIMARY KEY,
        threshold_kg REAL NOT NULL,
        earned_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """,
    """
    CREATE TABLE notifications_sent (
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (date, type)
    );
    """,
    """
    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
)

LEGACY_SETTINGS: tuple[tuple[str, str], ...] = (
    ("target_weight", "70.0"),
    ("height_cm", "175.0"),
    ("tip_time", "09:00"),
    ("reminder_time", "20:00"),
    ("exercise_time", "17:00"),
    ("reminder_weekday", "1"),
)


def _seed_legacy_db(db_path: str) -> None:
    """Create a legacy single-user database with real-looking data."""
    db = Database(db_path)
    try:
        for statement in LEGACY_DDL:
            db.conn.execute(statement)
        for key, value in LEGACY_SETTINGS:
            db.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)", (key, value)
            )
        db.conn.execute(
            "INSERT INTO weight_entries (date, weight_kg, created_at)"
            " VALUES ('2026-08-01', 100.0, '2026-08-01 09:00:00')"
        )
        db.conn.execute(
            "INSERT INTO weight_entries (date, weight_kg, created_at)"
            " VALUES ('2026-08-02', 95.0, '2026-08-02 09:00:00')"
        )
        db.conn.execute(
            "INSERT INTO push_subscriptions (endpoint, p256dh, auth)"
            " VALUES ('https://push.example.com/legacy', 'p256', 'auth')"
        )
        db.conn.execute(
            "INSERT INTO active_rewards (checkpoint_percent, threshold_kg, earned_at)"
            " VALUES (10, 98.0, '2026-08-02 09:00:00')"
        )
        db.conn.execute(
            "INSERT INTO notifications_sent (date, type, sent_at)"
            " VALUES ('2026-08-02', 'tip', '2026-08-02 09:00:00')"
        )
    finally:
        db.close()


def _count_where(db: Database, table: str, user_id: int) -> int:
    row = db.conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)
    ).fetchone()
    return int(row[0])


def _has_user_column(db: Database, table: str) -> bool:
    columns = {
        row["name"]
        for row in db.conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    return "user_id" in columns


# ---- migration itself -----------------------------------------------------


@pytest.mark.asyncio
async def test_boot_migrates_legacy_schema_discarding_rows(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    _seed_legacy_db(db_path)

    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    db = app.state.db

    # Every table gained the user_id column.
    for table in (
        "weight_entries",
        "push_subscriptions",
        "active_rewards",
        "notifications_sent",
        "settings",
    ):
        assert _has_user_column(db, table), table

    # Legacy pre-auth rows are DISCARDED: no user owns them and no account
    # should inherit smoke-test artifacts. Every table is empty.
    assert db.conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM weight_entries").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM notifications_sent").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM active_rewards").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_migration_is_idempotent_across_reboots(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    _seed_legacy_db(db_path)

    for _ in range(2):
        app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
        init_app_state(app, db_path=db_path, vapid_path=vapid_path)
        db = app.state.db
        assert db.conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0
        assert db.conn.execute("SELECT COUNT(*) FROM weight_entries").fetchone()[0] == 0


def test_fresh_db_creates_user_columns_directly(tmp_path):
    db = Database(str(tmp_path / "fresh.db"))
    db.init_schema()
    try:
        for table in (
            "weight_entries",
            "push_subscriptions",
            "active_rewards",
            "notifications_sent",
            "settings",
        ):
            assert _has_user_column(db, table), table
        assert db.list_users() == []
    finally:
        db.close()


def test_users_table_gains_email_column_idempotently(tmp_path):
    """A database created before password-reset support (users without an
    email column) gains it on boot, preserving existing accounts; a second
    boot leaves the schema untouched."""
    db_path = str(tmp_path / "pre_email.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    pre = Database(db_path)
    with pre._tx() as conn:
        conn.execute(
            "CREATE TABLE users ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " username TEXT NOT NULL UNIQUE,"
            " password_hash TEXT NOT NULL,"
            " salt TEXT NOT NULL,"
            " created_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        conn.execute(
            "CREATE TABLE sessions ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
            " token_hash TEXT NOT NULL UNIQUE,"
            " created_at TEXT NOT NULL DEFAULT (datetime('now')),"
            " expires_at TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "INSERT INTO users (username, password_hash, salt)"
            " VALUES ('legacy_user', 'hash', 'salt')"
        )
    pre.close()

    for _ in range(2):
        app = create_app(
            db_path=db_path, vapid_path=vapid_path, start_scheduler=False
        )
        init_app_state(app, db_path=db_path, vapid_path=vapid_path)
        db = app.state.db
        columns = {
            row["name"]
            for row in db.conn.execute("PRAGMA table_info(users)").fetchall()
        }
        assert "email" in columns
        # the pre-existing account survives with a NULL email
        user = db.get_user_by_username("legacy_user")
        assert user is not None
        assert user.email is None


# ---- every new account starts empty --------------------------------------


def test_first_user_starts_empty(tmp_path):
    db = Database(str(tmp_path / "fresh.db"))
    db.init_schema()
    try:
        alice = db.create_user("alice", "hash", "salt")
        for table in (
            "settings",
            "weight_entries",
            "push_subscriptions",
            "notifications_sent",
            "active_rewards",
        ):
            assert _count_where(db, table, alice.id) == 0, table
    finally:
        db.close()


@pytest.mark.asyncio
async def test_registered_users_start_empty_after_migration(tmp_path):
    """End-to-end: after migrating a legacy DB, every registrant (first and
    later) starts with empty data and sets their own settings."""
    db_path = str(tmp_path / "legacy.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    _seed_legacy_db(db_path)

    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={
                "username": "alice",
                "password": "password123",
                "email": "alice@example.com",
            },
        )
        assert resp.status_code == 201
        alice_id = resp.json()["id"]

        # Alice starts with empty data — no legacy backfill.
        settings = (await ac.get("/api/settings")).json()
        assert settings["target_weight"] is None
        assert settings["height_cm"] is None
        weight = (await ac.get("/api/weight")).json()
        assert weight["entries"] == []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as bc:
        resp = await bc.post(
            "/api/auth/register",
            json={
                "username": "bob",
                "password": "password123",
                "email": "bob@example.com",
            },
        )
        assert resp.status_code == 201
        bob_id = resp.json()["id"]

        # Bob also starts empty; nothing was inherited by either account.
        settings = (await bc.get("/api/settings")).json()
        assert settings["target_weight"] is None
        weight = (await bc.get("/api/weight")).json()
        assert weight["entries"] == []
        for table in (
            "settings",
            "weight_entries",
            "push_subscriptions",
            "notifications_sent",
            "active_rewards",
        ):
            assert _count_where(app.state.db, table, alice_id) == 0, table
            assert _count_where(app.state.db, table, bob_id) == 0, table
