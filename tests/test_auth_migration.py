"""Legacy single-user DB migration: user_id columns, transactional table
rebuilds, and the one-shot first-registrant backfill of sentinel-owned rows.

Seeds a database with the pre-auth schema (no user_id anywhere), boots the app
so init_schema migrates it, then registers users to prove the first account
claims every legacy row atomically and later accounts get empty data.
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
async def test_boot_migrates_legacy_schema_preserving_rows(tmp_path):
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

    # Data survived the rebuilds, still sentinel-owned (no users exist yet).
    assert db.conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 6
    assert db.conn.execute("SELECT COUNT(*) FROM weight_entries").fetchone()[0] == 2
    assert db.conn.execute("SELECT COUNT(*) FROM push_subscriptions").fetchone()[0] == 1
    assert db.conn.execute("SELECT COUNT(*) FROM notifications_sent").fetchone()[0] == 1
    assert _count_where(db, "settings", 0) == 6
    assert _count_where(db, "weight_entries", 0) == 2


@pytest.mark.asyncio
async def test_migration_is_idempotent_across_reboots(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    _seed_legacy_db(db_path)

    for _ in range(2):
        app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
        init_app_state(app, db_path=db_path, vapid_path=vapid_path)
        db = app.state.db
        assert db.conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 6
        assert db.conn.execute("SELECT COUNT(*) FROM weight_entries").fetchone()[0] == 2


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


# ---- first-registrant backfill -------------------------------------------


def test_first_user_claims_sentinel_rows_atomically(tmp_path):
    db = Database(str(tmp_path / "backfill.db"))
    db.init_schema()
    try:
        with db._tx() as conn:
            conn.execute(
                "INSERT INTO settings (user_id, key, value) VALUES (0, 'target_weight', '70.0')"
            )
            conn.execute(
                "INSERT INTO weight_entries (user_id, date, weight_kg)"
                " VALUES (0, '2026-08-01', 100.0)"
            )
            conn.execute(
                "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)"
                " VALUES (0, 'https://push.example.com/s', 'p', 'a')"
            )
            conn.execute(
                "INSERT INTO notifications_sent (user_id, date, type)"
                " VALUES (0, '2026-08-02', 'tip')"
            )
            conn.execute(
                "INSERT INTO active_rewards (user_id, checkpoint_percent, threshold_kg)"
                " VALUES (0, 10, 98.0)"
            )

        alice = db.create_user("alice", "hash", "salt")
        for table in (
            "settings",
            "weight_entries",
            "push_subscriptions",
            "notifications_sent",
            "active_rewards",
        ):
            assert _count_where(db, table, alice.id) == 1, table
            assert _count_where(db, table, 0) == 0, table
    finally:
        db.close()


def test_later_user_cannot_claim_existing_rows(tmp_path):
    db = Database(str(tmp_path / "backfill.db"))
    db.init_schema()
    try:
        with db._tx() as conn:
            conn.execute(
                "INSERT INTO settings (user_id, key, value) VALUES (0, 'target_weight', '70.0')"
            )
        alice = db.create_user("alice", "hash", "salt")
        bob = db.create_user("bob", "hash", "salt")

        # bob's registration must not move or copy alice's claimed settings.
        assert _count_where(db, "settings", alice.id) == 1
        assert _count_where(db, "settings", bob.id) == 0
        row = db.conn.execute(
            "SELECT value FROM settings WHERE user_id = ? AND key = 'target_weight'",
            (alice.id,),
        ).fetchone()
        assert row is not None and row[0] == "70.0"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_first_registrant_claims_legacy_rows_via_api(tmp_path):
    """End-to-end: a legacy DB's settings survive for the first account and
    later accounts start empty — the spec's backfill scenarios."""
    db_path = str(tmp_path / "legacy.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    _seed_legacy_db(db_path)

    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        assert resp.status_code == 201
        alice_id = resp.json()["id"]

        # Alice's API view reflects the claimed legacy data.
        settings = (await ac.get("/api/settings")).json()
        assert settings["target_weight"] == 70.0
        assert settings["height_cm"] == 175.0
        weight = (await ac.get("/api/weight")).json()
        assert [entry["date"] for entry in weight["entries"]] == [
            "2026-08-02",
            "2026-08-01",
        ]

        # All five tables now belong to alice; nothing stays sentinel-owned.
        for table in (
            "weight_entries",
            "push_subscriptions",
            "active_rewards",
            "notifications_sent",
            "settings",
        ):
            assert _count_where(app.state.db, table, alice_id) > 0, table
            assert _count_where(app.state.db, table, 0) == 0, table

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as bc:
        resp = await bc.post(
            "/api/auth/register",
            json={"username": "bob", "password": "password123"},
        )
        assert resp.status_code == 201
        bob_id = resp.json()["id"]

        # Bob starts with empty data; alice's legacy settings are untouched.
        settings = (await bc.get("/api/settings")).json()
        assert settings["target_weight"] is None
        weight = (await bc.get("/api/weight")).json()
        assert weight["entries"] == []
        assert _count_where(app.state.db, "settings", bob_id) == 0
        assert _count_where(app.state.db, "settings", alice_id) == 6
