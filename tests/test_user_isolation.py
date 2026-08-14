"""Per-user isolation: user A must never see, modify, or send to user B's data.

Covers the spec's cross-user scenarios through the API (two authenticated
clients on one app) plus direct-DB scoping checks and the universal 401
contract for unauthenticated access. Every Database method takes a leading
user_id; any missed scoping shows up here as a leaked or mutated row.
"""

from datetime import date, timedelta

import pytest

from database import Database
from main import create_app, init_app_state
from constants import QUEST_POOL
import database as database_module
import routes as routes_module
import weekly
from tests.conftest import (
    auth_user_id,
    make_user,
    mark_done,
    register_user,
    seed_met_week,
)

SUBSCRIBE_BODY = {
    "endpoint": "https://push.example.com/v1/isolated",
    "p256dh": "BEl62iUYgUivxIkv69yViEuiBIa_IbT8n1sWj3N5nPw",
    "auth": "F8UVa5fTzFQXlq6dZ0Gt7g",
}


# ---- unauthenticated requests return 401 without changing state ----------


@pytest.mark.asyncio
async def test_401_on_weight_get(client):
    assert (await client.get("/api/weight")).status_code == 401


@pytest.mark.asyncio
async def test_401_on_weight_post_does_not_create_entry(client, app):
    resp = await client.post(
        "/api/weight", json={"date": "2026-08-01", "weight_kg": 90.0}
    )
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM weight_entries"
    ).fetchone()[0]
    assert count == 0  # the request disclosed and changed nothing


@pytest.mark.asyncio
async def test_401_on_weight_delete(client, app):
    # Even a real entry id must not be touchable without a session.
    db = app.state.db
    with db._tx() as conn:
        conn.execute(
            "INSERT INTO weight_entries (user_id, date, weight_kg)"
            " VALUES (0, '2026-08-01', 90.0)"
        )
        row = conn.execute("SELECT id FROM weight_entries").fetchone()
    resp = await client.delete(f"/api/weight/{row['id']}")
    assert resp.status_code == 401
    assert db.conn.execute("SELECT COUNT(*) FROM weight_entries").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_401_on_rewards(client):
    assert (await client.get("/api/rewards")).status_code == 401


@pytest.mark.asyncio
async def test_401_on_settings_get(client):
    assert (await client.get("/api/settings")).status_code == 401


@pytest.mark.asyncio
async def test_401_on_settings_put_does_not_mutate(client, app):
    resp = await client.put("/api/settings", json={"target_weight": 80.0})
    assert resp.status_code == 401
    count = app.state.db.conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    assert count == 0


@pytest.mark.asyncio
async def test_401_on_push_subscribe(client, app):
    resp = await client.post("/api/push/subscribe", json=SUBSCRIBE_BODY)
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM push_subscriptions"
    ).fetchone()[0]
    assert count == 0


@pytest.mark.asyncio
async def test_401_on_push_unsubscribe(client):
    resp = await client.post(
        "/api/push/unsubscribe", json={"endpoint": SUBSCRIBE_BODY["endpoint"]}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_401_on_push_test(client):
    assert (await client.post("/api/push/test")).status_code == 401


@pytest.mark.asyncio
async def test_401_on_manual_notify(client):
    assert (await client.post("/api/notify/tip")).status_code == 401


@pytest.mark.asyncio
async def test_vapid_public_key_stays_public(client):
    # The VAPID public key is not user data (and the SPA needs it before
    # authentication for push registration), so it must NOT require a session.
    resp = await client.get("/api/push/vapid-public-key")
    assert resp.status_code == 200
    assert len(resp.json()["public_key"]) > 20


# ---- weight entries: read/upsert/delete isolation ------------------------


@pytest.mark.asyncio
async def test_entries_are_isolated_between_users(pair):
    alice, bob = pair
    await alice.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await alice.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})

    bob_data = (await bob.get("/api/weight")).json()
    assert bob_data["entries"] == []
    assert bob_data["summary"]["baseline_kg"] is None
    assert bob_data["summary"]["current_kg"] is None

    alice_data = (await alice.get("/api/weight")).json()
    assert [entry["date"] for entry in alice_data["entries"]] == [
        "2026-08-02",
        "2026-08-01",
    ]


@pytest.mark.asyncio
async def test_same_date_allowed_for_two_users(pair, app):
    alice, bob = pair
    await alice.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await bob.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 80.0})

    # The UNIQUE(user_id, date) rebuild: both rows coexist with correct owners.
    rows = app.state.db.conn.execute(
        "SELECT user_id, weight_kg FROM weight_entries WHERE date = '2026-08-01'"
    ).fetchall()
    assert len(rows) == 2
    assert {row["weight_kg"] for row in rows} == {100.0, 80.0}

    alice_data = (await alice.get("/api/weight")).json()
    assert [entry["weight_kg"] for entry in alice_data["entries"]] == [100.0]


@pytest.mark.asyncio
async def test_cross_user_delete_returns_404_and_preserves_entry(pair, app):
    alice, bob = pair
    created = (
        await alice.post(
            "/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0}
        )
    ).json()

    resp = await bob.delete(f"/api/weight/{created['id']}")
    assert resp.status_code == 404  # no information leak about the id

    alice_data = (await alice.get("/api/weight")).json()
    assert [entry["id"] for entry in alice_data["entries"]] == [created["id"]]


# ---- settings isolation ---------------------------------------------------


@pytest.mark.asyncio
async def test_settings_are_isolated_between_users(pair):
    alice, bob = pair
    res = await alice.put("/api/settings", json={"target_weight": 80.0})
    assert res.status_code == 200

    bob_settings = (await bob.get("/api/settings")).json()
    assert bob_settings["target_weight"] is None
    assert bob_settings["tip_time"] == "09:00"  # untouched defaults

    alice_settings = (await alice.get("/api/settings")).json()
    assert alice_settings["target_weight"] == 80.0


# ---- rewards isolation ----------------------------------------------------


@pytest.mark.asyncio
async def test_rewards_derive_only_from_own_data(pair, app):
    alice, bob = pair
    await alice.put("/api/settings", json={"target_weight": 80.0})
    await alice.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await alice.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})

    alice_rewards = (await alice.get("/api/rewards")).json()
    assert [cp["percent"] for cp in alice_rewards["active_checkpoints"]] == [10, 25]

    bob_rewards = (await bob.get("/api/rewards")).json()
    assert bob_rewards["active_checkpoints"] == []
    assert bob_rewards["earned_count"] == 0

    # The persisted rows are scoped: only alice owns active rewards.
    alice_id = app.state.db.get_user_by_username("alice").id
    bob_id = app.state.db.get_user_by_username("bob").id
    assert len(app.state.db.list_active_rewards(alice_id)) == 2
    assert app.state.db.list_active_rewards(bob_id) == []


@pytest.mark.asyncio
async def test_same_checkpoint_can_exist_for_two_users(pair, app):
    alice, bob = pair
    await alice.put("/api/settings", json={"target_weight": 80.0})
    await alice.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await alice.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    await bob.put("/api/settings", json={"target_weight": 60.0})
    await bob.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await bob.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    await bob.post("/api/weight", json={"date": "2026-08-03", "weight_kg": 90.0})

    # Both earn the 25% checkpoint independently, each with its own row whose
    # threshold reflects that user's own target (alice 92.5 vs bob 90.0).
    alice_id = app.state.db.get_user_by_username("alice").id
    bob_id = app.state.db.get_user_by_username("bob").id
    alice_rows = {
        r["checkpoint_percent"]: r["threshold_kg"]
        for r in app.state.db.list_active_rewards(alice_id)
    }
    bob_rows = {
        r["checkpoint_percent"]: r["threshold_kg"]
        for r in app.state.db.list_active_rewards(bob_id)
    }
    assert set(alice_rows) == {10, 25}
    assert set(bob_rows) == {10, 25}
    assert alice_rows[10] == 98.0  # 100 - 0.10*(100-80)
    assert bob_rows[10] == 96.0  # 100 - 0.10*(100-60)
    assert alice_rows[25] == 95.0  # 100 - 0.25*(100-80)
    assert bob_rows[25] == 90.0  # 100 - 0.25*(100-60)


# ---- subscriptions isolation ----------------------------------------------


@pytest.mark.asyncio
async def test_push_test_targets_only_own_subscriptions(pair, stub_push):
    alice, bob = pair
    await alice.post("/api/push/subscribe", json=SUBSCRIBE_BODY)

    bob_res = await bob.post("/api/push/test")
    assert bob_res.status_code == 200
    assert bob_res.json() == {"sent": 0, "total": 0}

    alice_res = await alice.post("/api/push/test")
    assert alice_res.json() == {"sent": 1, "total": 1}
    assert [call["endpoint"] for call in stub_push] == [SUBSCRIBE_BODY["endpoint"]]


@pytest.mark.asyncio
async def test_unsubscribe_only_removes_own_subscription(pair, app):
    alice, bob = pair
    await alice.post("/api/push/subscribe", json=SUBSCRIBE_BODY)

    # Bob cannot remove alice's subscription (scoped DELETE).
    resp = await bob.post(
        "/api/push/unsubscribe", json={"endpoint": SUBSCRIBE_BODY["endpoint"]}
    )
    assert resp.status_code == 200
    assert resp.json() == {"removed": False}
    alice_id = app.state.db.get_user_by_username("alice").id
    assert len(app.state.db.list_subscriptions(alice_id)) == 1


@pytest.mark.asyncio
async def test_manual_notify_targets_only_own_subscriptions(pair, stub_push):
    alice, bob = pair
    await alice.post("/api/push/subscribe", json=SUBSCRIBE_BODY)

    bob_res = await bob.post("/api/notify/tip")
    assert bob_res.json() == {"sent": 0, "total": 0}

    alice_res = await alice.post("/api/notify/tip")
    assert alice_res.json() == {"sent": 1, "total": 1}


# ---- direct-DB scoping (guards every scoped method) -----------------------


def test_db_upsert_and_get_scoped_by_user(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice")
        bob = make_user(db, "bob")
        db.upsert_entry(alice.id, "2026-08-01", 100.0)
        db.upsert_entry(bob.id, "2026-08-01", 80.0)

        alice_entry = db.get_entry_by_date(alice.id, "2026-08-01")
        bob_entry = db.get_entry_by_date(bob.id, "2026-08-01")
        assert alice_entry is not None and alice_entry.weight_kg == 100.0
        assert bob_entry is not None and bob_entry.weight_kg == 80.0
        assert [e.weight_kg for e in db.list_entries(alice.id)] == [100.0]
    finally:
        db.close()


def test_db_delete_entry_scoped_by_user(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice")
        bob = make_user(db, "bob")
        entry = db.upsert_entry(alice.id, "2026-08-01", 100.0)

        assert db.delete_entry(bob.id, entry.id) is False  # not bob's to delete
        assert db.get_entry_by_date(alice.id, "2026-08-01") is not None
        assert db.delete_entry(alice.id, entry.id) is True
    finally:
        db.close()


def test_db_settings_scoped_by_user(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice")
        bob = make_user(db, "bob")
        db.update_settings(alice.id, {"target_weight": 80.0})
        assert db.get_settings(alice.id).target_weight == 80.0
        assert db.get_settings(bob.id).target_weight is None
    finally:
        db.close()


def test_db_subscription_methods_scoped_by_user(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice")
        bob = make_user(db, "bob")
        db.add_subscription(alice.id, "https://push.example.com/a", "p", "a")

        assert [s.endpoint for s in db.list_subscriptions(alice.id)] == [
            "https://push.example.com/a"
        ]
        assert db.list_subscriptions(bob.id) == []
        assert db.remove_subscription(bob.id, "https://push.example.com/a") is False
        assert db.remove_subscription(alice.id, "https://push.example.com/a") is True
    finally:
        db.close()


def test_db_dedupe_scoped_by_user(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice")
        bob = make_user(db, "bob")
        db.mark_notification_sent(alice.id, "2026-08-02", "tip")
        assert db.is_notification_sent(alice.id, "2026-08-02", "tip") is True
        # bob's same-date key is independent (user-scoped dedupe)
        assert db.is_notification_sent(bob.id, "2026-08-02", "tip") is False
    finally:
        db.close()


def test_db_list_users_returns_all_ordered(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        assert db.list_users() == []
        first = make_user(db, "alice")
        second = make_user(db, "bob")
        users = db.list_users()
        assert [u.id for u in users] == [first.id, second.id]
        assert [u.username for u in users] == ["alice", "bob"]
    finally:
        db.close()


def test_db_startup_reconcile_is_per_user(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice")
        bob = make_user(db, "bob")
        # Alice earns two checkpoints; bob has only a stale row.
        db.update_settings(alice.id, {"target_weight": 80.0})
        db.upsert_entry(alice.id, "2026-08-01", 100.0)
        db.upsert_entry(alice.id, "2026-08-02", 95.0)
        with db._tx() as conn:
            conn.execute(
                "INSERT INTO active_rewards (user_id, checkpoint_percent, threshold_kg)"
                " VALUES (?, 100, 80.0)",
                (bob.id,),
            )

        db.reconcile_active_rewards()  # the startup path

        assert {r["checkpoint_percent"] for r in db.list_active_rewards(alice.id)} == {10, 25}
        assert db.list_active_rewards(bob.id) == []  # stale row revoked
    finally:
        db.close()


def test_db_upsert_reconciles_only_own_rewards(tmp_path):
    db = Database(str(tmp_path / "scope.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice")
        bob = make_user(db, "bob")
        db.update_settings(alice.id, {"target_weight": 80.0})
        db.update_settings(bob.id, {"target_weight": 90.0})
        db.upsert_entry(alice.id, "2026-08-01", 100.0)
        db.upsert_entry(alice.id, "2026-08-02", 95.0)
        db.upsert_entry(bob.id, "2026-08-01", 100.0)
        db.upsert_entry(bob.id, "2026-08-02", 95.0)

        # Alice's mutation reconciled alice; bob's thresholds differ (target 90)
        # and both keep their own earned rows.
        alice_rows = {
            (r["checkpoint_percent"], r["threshold_kg"])
            for r in db.list_active_rewards(alice.id)
        }
        bob_rows = {
            (r["checkpoint_percent"], r["threshold_kg"])
            for r in db.list_active_rewards(bob.id)
        }
        # start 100: 10% checkpoint = 100 - 0.10*(100-target)
        assert (10, 98.0) in alice_rows  # target 80
        assert (10, 99.0) in bob_rows  # target 90
        assert alice_rows != bob_rows
    finally:
        db.close()


# ---- weekly objectives (r2-completion · S2) --------------------------------


@pytest.mark.asyncio
async def test_401_on_weekly(client):
    assert (await client.get("/api/weekly")).status_code == 401


@pytest.mark.asyncio
async def test_weekly_state_and_awards_isolated_between_users(pair, app):
    """A user's activation, paid awards, and weekly history never leak into
    another user's state or XP."""
    alice, bob = pair
    db = app.state.db
    alice_user = db.get_user_by_username("alice")
    bob_user = db.get_user_by_username("bob")
    assert alice_user is not None and bob_user is not None
    monday = weekly.week_start(date.today())
    prev = monday - timedelta(days=7)
    db.stamp_weekly_activation(alice_user.id, f"{prev.isoformat()} 09:00:00")
    seed_met_week(db, alice_user.id, prev)
    xp_before = db.total_xp_for_user(alice_user.id)
    alice_data = (await alice.get("/api/weekly")).json()
    assert alice_data["met_flips"] == ["quests", "good_days"]
    assert db.total_xp_for_user(alice_user.id) == xp_before + 80
    # Bob's weekly state shows no flips and none of alice's paid weeks.
    bob_data = (await bob.get("/api/weekly")).json()
    assert bob_data["met_flips"] == []
    assert db.total_xp_for_user(bob_user.id) == 0
    assert all(
        not goal["awarded"] for entry in bob_data["history"] for goal in entry["goals"]
    )
    # The current week is the same calendar week for both users.
    assert alice_data["current"]["week_start"] == bob_data["current"]["week_start"]


@pytest.mark.asyncio
async def test_weekly_mutation_award_isolated_between_users(pair, app, monkeypatch):
    """R6 isolation: alice's tenth-completion award pays alice only — bob's
    weekly_awards and XP stay untouched by her mutation."""
    fixed = date(2026, 8, 5)  # Wednesday; week starts Mon 2026-08-03

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(database_module, "date", _FixedDate)
    monkeypatch.setattr(routes_module, "date", _FixedDate)
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-05 09:00:00")
    alice, bob = pair
    db = app.state.db
    alice_user = db.get_user_by_username("alice")
    bob_user = db.get_user_by_username("bob")
    assert alice_user is not None and bob_user is not None
    monday = weekly.week_start(fixed)
    db.stamp_weekly_activation(alice_user.id, f"{monday.isoformat()} 09:00:00")
    mark_done(db, alice_user.id, monday, [entry[0] for entry in QUEST_POOL])
    mark_done(
        db,
        alice_user.id,
        monday + timedelta(days=1),
        ["exercise_10", "log_meal", "streak_alive"],
    )
    mark_done(db, bob_user.id, monday, ["mood_checkin"])  # bob: 1 / 10
    alice_xp_before = db.total_xp_for_user(alice_user.id)
    bob_xp_before = db.total_xp_for_user(bob_user.id)
    alice_quests = (await alice.get("/api/quests")).json()["quests"]
    target = alice_quests[0]
    assert (
        await alice.post(f"/api/quests/{target['id']}/complete")
    ).status_code == 200
    # Alice's tenth completion pays alice's quests award immediately.
    assert (
        db.total_xp_for_user(alice_user.id)
        == alice_xp_before + target["xp_value"] + 40
    )
    # Bob: no cross-user award, no XP change, no weekly_awards rows.
    assert db.total_xp_for_user(bob_user.id) == bob_xp_before
    with db._tx() as conn:
        bob_rows = conn.execute(
            "SELECT user_id, goal FROM weekly_awards WHERE user_id = ?",
            (bob_user.id,),
        ).fetchall()
    assert bob_rows == []


def test_db_startup_weekly_reconcile_pays_due_awards(tmp_path):
    """Startup reconciliation (reconcile_all_weekly_awards — the init_app_state
    entry point) pays due awards for activated users only, idempotently."""
    db = Database(str(tmp_path / "weekly.db"))
    db.init_schema()
    try:
        alice = make_user(db, "alice-weekly")
        bob = make_user(db, "bob-weekly")
        monday = weekly.week_start(date.today())
        prev = monday - timedelta(days=7)
        db.stamp_weekly_activation(alice.id, f"{prev.isoformat()} 09:00:00")
        seed_met_week(db, alice.id, prev)
        # Bob is never activated: startup reconciliation must skip him even
        # though his week is met.
        seed_met_week(db, bob.id, prev)
        alice_before = db.total_xp_for_user(alice.id)
        bob_before = db.total_xp_for_user(bob.id)
        db.reconcile_all_weekly_awards()
        assert db.total_xp_for_user(alice.id) == alice_before + 80
        assert db.total_xp_for_user(bob.id) == bob_before
        # A second run is a no-op (exactly-once persistence).
        db.reconcile_all_weekly_awards()
        assert db.total_xp_for_user(alice.id) == alice_before + 80
    finally:
        db.close()


# ---- collectibles (r2-completion · S4) --------------------------------------


@pytest.mark.asyncio
async def test_401_on_collectibles(client):
    assert (await client.get("/api/collectibles")).status_code == 401


@pytest.mark.asyncio
async def test_collectibles_isolated_between_users(pair, app):
    """Alice's earned shelf never leaks into Bob's: Bob's collectibles stay
    all locked even though Alice earned tokens (per-user derivation)."""
    alice, bob = pair
    db = app.state.db
    alice_user = db.get_user_by_username("alice")
    assert alice_user is not None
    monday = weekly.week_start(date.today())
    await alice.put("/api/settings", json={"target_weight": 80.0, "height_cm": 175.0})
    db.upsert_entry(alice_user.id, (monday - timedelta(days=1)).isoformat(), 100.0)
    db.upsert_entry(alice_user.id, monday.isoformat(), 90.0)
    seed_met_week(db, alice_user.id, monday)
    alice_by_key = {i["key"]: i for i in (await alice.get("/api/collectibles")).json()["collectibles"]}
    bob_items = (await bob.get("/api/collectibles")).json()["collectibles"]
    assert alice_by_key["checkpoint_10"]["earned"] is True
    assert alice_by_key["weekly_quests"]["earned"] is True
    assert all(not i["earned"] and i["unlocked_at"] is None for i in bob_items)
