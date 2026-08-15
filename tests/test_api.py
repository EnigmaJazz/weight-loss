"""API tests: weight summary, settings roundtrip, push endpoints, rewards."""

import sqlite3
from datetime import date, timedelta

import pytest
from fastapi import FastAPI

from constants import COLLECTIBLE_CATALOG, QUEST_POOL
import database as database_module
import quests
from models import AppSettings
import routes as routes_module
import weekly
from tests.conftest import (
    ONBOARDED_USERNAME,
    auth_user_id,
    make_user,
    mark_done,
    pair,
    seed_met_week,
)

SUBSCRIBE_BODY = {
    "endpoint": "https://push.example.com/v1/abcd1234",
    "p256dh": "BEl62iUYgUivxIkv69yViEuiBIa_IbT8n1sWj3N5nPw",
    "auth": "F8UVa5fTzFQXlq6dZ0Gt7g",
}


def _onboarded_user_id(app: FastAPI) -> int:
    """The user id of the account the onboarded_client fixture registered."""
    user = app.state.db.get_user_by_username(ONBOARDED_USERNAME)
    assert user is not None
    return user.id


@pytest.mark.asyncio
async def test_weight_empty(auth_client):
    data = (await auth_client.get("/api/weight")).json()
    assert data["entries"] == []
    assert data["summary"]["baseline_kg"] is None
    assert data["summary"]["current_kg"] is None
    assert data["summary"]["lost_kg"] is None


@pytest.mark.asyncio
async def test_settings_get_returns_defaults(auth_client):
    data = (await auth_client.get("/api/settings")).json()
    assert "milestone_step_kg" not in data
    assert data["height_cm"] is None
    assert data["tip_time"] == "09:00"
    assert data["reminder_time"] == "20:00"
    assert data["exercise_time"] == "17:00"
    assert data["target_weight"] is None
    assert data["target_bmi"] is None
    assert data["onboarding_complete"] is False
    assert data["start_weight_override"] is None


@pytest.mark.asyncio
async def test_onboarded_client_completed_onboarding(app, onboarded_client):
    # Fixture contract: the helper's wizard simulation leaves a ready tracker —
    # settings hold the defaults and today's first weight entry exists.
    data = (await onboarded_client.get("/api/settings")).json()
    assert data["height_cm"] == 175
    assert data["target_weight"] == 70.0
    assert data["target_bmi"] is None
    weight = (await onboarded_client.get("/api/weight")).json()
    assert weight["summary"]["baseline_kg"] == 80.0
    assert weight["summary"]["current_kg"] == 80.0


@pytest.mark.asyncio
async def test_settings_put_partial_update(auth_client):
    res = await auth_client.put("/api/settings", json={"target_weight": 80.0})
    assert res.status_code == 200
    body = res.json()
    assert body["target_weight"] == 80.0
    assert body["height_cm"] is None

    got = (await auth_client.get("/api/settings")).json()
    assert got["target_weight"] == 80.0


@pytest.mark.asyncio
async def test_settings_clear_override_with_null(auth_client):
    await auth_client.put("/api/settings", json={"target_weight": 80.0})
    await auth_client.put("/api/settings", json={"target_weight": None})
    got = (await auth_client.get("/api/settings")).json()
    assert got["target_weight"] is None


@pytest.mark.asyncio
async def test_settings_bad_time_rejected(auth_client):
    res = await auth_client.put("/api/settings", json={"tip_time": "25:99"})
    assert res.status_code == 422
    res = await auth_client.put("/api/settings", json={"reminder_time": "not-a-time"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_settings_retired_key_rejected(auth_client):
    # Spec: the retired milestone_step_kg setting must be rejected and must not
    # change the stored settings.
    await auth_client.put("/api/settings", json={"target_weight": 80.0})
    res = await auth_client.put("/api/settings", json={"milestone_step_kg": 2.0})
    assert res.status_code == 422
    got = (await auth_client.get("/api/settings")).json()
    assert got["target_weight"] == 80.0
    assert "milestone_step_kg" not in got


@pytest.mark.asyncio
async def test_settings_save_height(auth_client):
    res = await auth_client.put("/api/settings", json={"height_cm": 175})
    assert res.status_code == 200
    assert res.json()["height_cm"] == 175
    got = (await auth_client.get("/api/settings")).json()
    assert got["height_cm"] == 175


@pytest.mark.asyncio
async def test_settings_nonpositive_height_rejected(auth_client):
    res = await auth_client.put("/api/settings", json={"height_cm": 0})
    assert res.status_code == 422
    res = await auth_client.put("/api/settings", json={"height_cm": -5})
    assert res.status_code == 422


# ---- per-user input units (per-user-default-units) -----------------------
# Contract: weight_unit/height_unit persist per user and round-trip; values
# outside the select options are rejected with 422; missing rows fall back to
# the kg / cm defaults.


@pytest.mark.asyncio
async def test_settings_unit_defaults(auth_client):
    data = (await auth_client.get("/api/settings")).json()
    assert data["weight_unit"] == "kg"
    assert data["height_unit"] == "cm"
    assert data["weight_display"] == "lb"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [("weight_unit", "st-lb"), ("height_unit", "ft-in"), ("weight_display", "st-lb")],
)
async def test_settings_unit_roundtrip(auth_client, field, value):
    res = await auth_client.put("/api/settings", json={field: value})
    assert res.status_code == 200
    assert res.json()[field] == value
    got = (await auth_client.get("/api/settings")).json()
    assert got[field] == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,bad",
    [
        ("weight_unit", "lb"),
        ("height_unit", "m"),
        ("weight_unit", "KG"),
        ("weight_display", "kg"),
        ("weight_display", "lbs"),
        ("weight_display", "ST-LB"),
    ],
)
async def test_settings_invalid_unit_rejected(auth_client, field, bad):
    res = await auth_client.put("/api/settings", json={field: bad})
    assert res.status_code == 422


# Contract: weight_display: null removes the override and restores the lb
# default, mirroring the notification-time null semantics.


@pytest.mark.asyncio
async def test_settings_weight_display_null_restores_default(auth_client):
    await auth_client.put("/api/settings", json={"weight_display": "st-lb"})
    res = await auth_client.put("/api/settings", json={"weight_display": None})
    assert res.status_code == 200
    got = (await auth_client.get("/api/settings")).json()
    assert got["weight_display"] == "lb"


# ---- theme preference (dark-mode) ----------------------------------------
# Contract: theme persists per user and round-trips; exactly the three states
# system|light|dark are accepted; invalid values are rejected with 422; null
# removes the override and restores the "system" default; missing rows fall
# back to the default.


@pytest.mark.asyncio
async def test_settings_theme_defaults_to_system(auth_client):
    data = (await auth_client.get("/api/settings")).json()
    assert data["theme"] == "system"


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ["dark", "light", "system"])
async def test_settings_theme_roundtrip(auth_client, theme):
    res = await auth_client.put("/api/settings", json={"theme": theme})
    assert res.status_code == 200
    assert res.json()["theme"] == theme
    got = (await auth_client.get("/api/settings")).json()
    assert got["theme"] == theme


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_theme", ["auto", "purple"])
async def test_settings_invalid_theme_rejected_without_mutation(auth_client, bad_theme):
    # Spec: invalid theme -> 422 and current settings remain unchanged.
    await auth_client.put("/api/settings", json={"theme": "dark"})
    res = await auth_client.put("/api/settings", json={"theme": bad_theme})
    assert res.status_code == 422
    got = (await auth_client.get("/api/settings")).json()
    assert got["theme"] == "dark"


@pytest.mark.asyncio
async def test_settings_theme_null_restores_default(auth_client):
    # Contract: null removes the override and restores the "system" default,
    # mirroring the notification-time null semantics.
    await auth_client.put("/api/settings", json={"theme": "dark"})
    res = await auth_client.put("/api/settings", json={"theme": None})
    assert res.status_code == 200
    assert res.json()["theme"] == "system"
    got = (await auth_client.get("/api/settings")).json()
    assert got["theme"] == "system"


@pytest.mark.asyncio
async def test_settings_theme_isolated_between_users(pair):
    # Spec: A persists dark, B stays system; neither observes the other's value.
    alice, bob = pair
    res = await alice.put("/api/settings", json={"theme": "dark"})
    assert res.status_code == 200
    assert res.json()["theme"] == "dark"

    bob_settings = (await bob.get("/api/settings")).json()
    assert bob_settings["theme"] == "system"

    alice_settings = (await alice.get("/api/settings")).json()
    assert alice_settings["theme"] == "dark"


# ---- accent colour preference (r2b-accent-colour) -----------------------
# Contract: accent persists per user and round-trips; exactly the five values
# purple|teal|blue|green|orange are accepted; invalid values are rejected with
# 422; null removes the override and restores the "green" default; missing rows
# fall back to the default.


@pytest.mark.asyncio
async def test_settings_accent_defaults_to_green(auth_client):
    data = (await auth_client.get("/api/settings")).json()
    assert data["accent"] == "green"


@pytest.mark.asyncio
@pytest.mark.parametrize("accent", ["purple", "teal", "blue", "green", "orange"])
async def test_settings_accent_roundtrip(auth_client, accent):
    res = await auth_client.put("/api/settings", json={"accent": accent})
    assert res.status_code == 200
    assert res.json()["accent"] == accent
    got = (await auth_client.get("/api/settings")).json()
    assert got["accent"] == accent


@pytest.mark.asyncio
async def test_settings_invalid_accent_rejected_without_mutation(auth_client):
    # Spec: invalid accent -> 422 and current settings remain unchanged.
    await auth_client.put("/api/settings", json={"accent": "teal"})
    res = await auth_client.put("/api/settings", json={"accent": "pink"})
    assert res.status_code == 422
    got = (await auth_client.get("/api/settings")).json()
    assert got["accent"] == "teal"


@pytest.mark.asyncio
async def test_settings_accent_null_restores_default(auth_client):
    # Contract: null removes the override and restores the "green" default,
    # mirroring the theme null semantics.
    await auth_client.put("/api/settings", json={"accent": "purple"})
    res = await auth_client.put("/api/settings", json={"accent": None})
    assert res.status_code == 200
    assert res.json()["accent"] == "green"
    got = (await auth_client.get("/api/settings")).json()
    assert got["accent"] == "green"


@pytest.mark.asyncio
async def test_settings_accent_isolated_between_users(pair):
    # Spec: A persists purple, B stays green; neither observes the other's value.
    alice, bob = pair
    res = await alice.put("/api/settings", json={"accent": "purple"})
    assert res.status_code == 200
    assert res.json()["accent"] == "purple"

    bob_settings = (await bob.get("/api/settings")).json()
    assert bob_settings["accent"] == "green"

    alice_settings = (await alice.get("/api/settings")).json()
    assert alice_settings["accent"] == "purple"


# ---- notification schedule disable (notification-schedule-disable) -----
# Contract: "" disables a schedule (persisted and round-tripped unchanged);
# null removes the override and restores the default; any other non-empty
# value is rejected with 422 without mutating the stored setting.


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["tip_time", "reminder_time", "exercise_time"])
async def test_settings_disable_time_with_empty_string(auth_client, field):
    res = await auth_client.put("/api/settings", json={field: ""})
    assert res.status_code == 200
    assert res.json()[field] == ""
    got = (await auth_client.get("/api/settings")).json()
    assert got[field] == ""
    defaults = {
        "tip_time": "09:00",
        "reminder_time": "20:00",
        "exercise_time": "17:00",
    }
    for other, default in defaults.items():
        if other != field:
            assert got[other] == default


@pytest.mark.asyncio
async def test_settings_null_restores_notification_default(auth_client):
    # null must remove the override, NOT disable: default is restored.
    res = await auth_client.put("/api/settings", json={"tip_time": "07:30"})
    assert res.status_code == 200
    assert res.json()["tip_time"] == "07:30"

    res = await auth_client.put("/api/settings", json={"tip_time": None})
    assert res.status_code == 200
    assert res.json()["tip_time"] == "09:00"
    got = (await auth_client.get("/api/settings")).json()
    assert got["tip_time"] == "09:00"


@pytest.mark.asyncio
@pytest.mark.parametrize("time_value", ["00:00", "23:59"])
async def test_settings_time_boundaries_accepted(auth_client, time_value):
    res = await auth_client.put("/api/settings", json={"tip_time": time_value})
    assert res.status_code == 200
    assert res.json()["tip_time"] == time_value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_value", ["24:00", "23:60", "9:00", "09:0", "not-a-time", "  "]
)
async def test_settings_invalid_times_rejected_without_mutation(auth_client, bad_value):
    # Invalid non-empty values return 422 and leave the stored value unchanged.
    await auth_client.put("/api/settings", json={"tip_time": "07:30"})
    res = await auth_client.put("/api/settings", json={"tip_time": bad_value})
    assert res.status_code == 422
    got = (await auth_client.get("/api/settings")).json()
    assert got["tip_time"] == "07:30"


@pytest.mark.asyncio
async def test_vapid_public_key(auth_client):
    data = (await auth_client.get("/api/push/vapid-public-key")).json()
    assert "public_key" in data
    assert len(data["public_key"]) > 20


@pytest.mark.asyncio
async def test_push_subscribe_bad_endpoint_rejected(auth_client):
    bad = {**SUBSCRIBE_BODY, "endpoint": "not-a-url"}
    res = await auth_client.post("/api/push/subscribe", json=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_push_subscribe_unsubscribe(auth_client, app):
    res = await auth_client.post("/api/push/subscribe", json=SUBSCRIBE_BODY)
    assert res.status_code == 201
    subs = app.state.db.list_subscriptions(auth_user_id(app))
    assert len(subs) == 1
    assert subs[0].endpoint == SUBSCRIBE_BODY["endpoint"]

    res = await auth_client.post(
        "/api/push/unsubscribe", json={"endpoint": SUBSCRIBE_BODY["endpoint"]}
    )
    assert res.status_code == 200
    assert res.json() == {"removed": True}
    assert app.state.db.list_subscriptions(auth_user_id(app)) == []


@pytest.mark.asyncio
async def test_push_test_sends_to_all(auth_client, stub_push):
    await auth_client.post("/api/push/subscribe", json=SUBSCRIBE_BODY)
    res = await auth_client.post("/api/push/test")
    assert res.status_code == 200
    body = res.json()
    assert body == {"sent": 1, "total": 1}
    assert len(stub_push) == 1
    assert "Test notification" in stub_push[0]["body"]


@pytest.mark.asyncio
async def test_manual_notify_endpoints(auth_client, stub_push):
    await auth_client.post("/api/push/subscribe", json=SUBSCRIBE_BODY)
    for notif_type in ("tip", "reminder", "exercise"):
        res = await auth_client.post(f"/api/notify/{notif_type}")
        assert res.status_code == 200
        assert res.json() == {"sent": 1, "total": 1}
    assert len(stub_push) == 3
    assert [call["notif_type"] for call in stub_push] == ["tip", "reminder", "exercise"]

    res = await auth_client.post("/api/notify/bogus")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_rewards_empty(auth_client):
    data = (await auth_client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []
    assert data["earned_count"] == 0
    assert data["next_checkpoint"] is None
    assert data["progress_to_next"] == 0.0


@pytest.mark.asyncio
async def test_rewards_checkpoints_earned_via_upserts(onboarded_client):
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    data = (await onboarded_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25]
    assert data["active_checkpoints"][0]["threshold_kg"] == 98.0
    assert data["active_checkpoints"][0]["earned_at"] is not None
    assert data["earned_count"] == 2
    nxt = data["next_checkpoint"]
    assert nxt["percent"] == 50
    assert nxt["threshold_kg"] == 90.0
    assert nxt["threshold_lb"] == pytest.approx(90 * 2.2046226218)
    assert nxt["threshold_stone"] == 14
    assert nxt["threshold_stone_lb"] == pytest.approx(90 * 2.2046226218 - 14 * 14)
    assert data["progress_to_next"] == 0.0


@pytest.mark.asyncio
async def test_rewards_regression_revokes_checkpoints(onboarded_client):
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-03", "weight_kg": 99.0})
    data = (await onboarded_client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []
    assert data["earned_count"] == 0
    nxt = data["next_checkpoint"]
    assert nxt["percent"] == 10
    assert nxt["threshold_kg"] == 98.0
    assert nxt["threshold_lb"] == pytest.approx(98 * 2.2046226218)
    assert nxt["threshold_stone"] == 15
    assert nxt["threshold_stone_lb"] == pytest.approx(98 * 2.2046226218 - 14 * 15)


@pytest.mark.asyncio
async def test_rewards_reenroll_refreshes_earned_at(onboarded_client, app, monkeypatch):
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-02 09:00:00")
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    user_id = _onboarded_user_id(app)
    rows = app.state.db.list_active_rewards(user_id)
    assert {r["checkpoint_percent"] for r in rows} == {10, 25}
    assert all(r["earned_at"] == "2026-08-02 09:00:00" for r in rows)

    # Regression revokes every checkpoint.
    await onboarded_client.post("/api/weight", json={"date": "2026-08-03", "weight_kg": 99.0})
    assert app.state.db.list_active_rewards(user_id) == []

    # Renewed progress re-earns with a NEW local timestamp.
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-04 18:30:00")
    await onboarded_client.post("/api/weight", json={"date": "2026-08-04", "weight_kg": 90.0})
    rows = app.state.db.list_active_rewards(user_id)
    assert {r["checkpoint_percent"] for r in rows} == {10, 25, 50}
    assert all(r["earned_at"] == "2026-08-04 18:30:00" for r in rows)


@pytest.mark.asyncio
async def test_rewards_historical_upsert_changes_start(onboarded_client):
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    data = (await onboarded_client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []

    # An earlier-dated entry moves the start (and thresholds) back to 100.
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    data = (await onboarded_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25]


@pytest.mark.asyncio
async def test_rewards_delete_reconciles(onboarded_client, app):
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    created = (await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})).json()
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    user_id = _onboarded_user_id(app)
    assert len(app.state.db.list_active_rewards(user_id)) == 2

    await onboarded_client.delete(f"/api/weight/{created['id']}")
    data = (await onboarded_client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []
    assert app.state.db.list_active_rewards(user_id) == []


@pytest.mark.asyncio
async def test_settings_update_reconciles_rewards(onboarded_client):
    # The onboarded fixture seeds a target, so clear it first: this test
    # exercises reconciliation from a no-target start.
    await onboarded_client.put("/api/settings", json={"target_weight": None})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    data = (await onboarded_client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []

    # Setting a target triggers reconciliation.
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    data = (await onboarded_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25]

    # Moving the override (start 100 -> 110) re-derives thresholds.
    await onboarded_client.put("/api/settings", json={"start_weight_override": 110.0})
    data = (await onboarded_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25, 50]


# ---- target_bmi reconciliation (target-progress-rewards) ----------------
# DB-level regressions: reward-affecting settings keys (target_bmi, height_cm)
# must recompute the persisted checkpoint set per user on change.


def _reward_rows(db: database_module.Database, user_id: int) -> list[tuple[int, float]]:
    """(percent, threshold_kg) pairs for a user's persisted checkpoints."""
    return [
        (r["checkpoint_percent"], r["threshold_kg"])
        for r in db.list_active_rewards(user_id)
    ]


@pytest.mark.asyncio
async def test_settings_target_bmi_reconciles_checkpoints(app):
    # Spec: GIVEN the 10% checkpoint active with target_weight 80 and start 100;
    # WHEN target_bmi 24 + height 175 are persisted and target_weight cleared
    # (resolved target 73.5 kg); THEN rewards recompute against 73.5.
    db = app.state.db
    user = make_user(db, "bmi-reconcile")
    db.upsert_entry(user.id, "2026-08-01", 100.0)
    db.upsert_entry(user.id, "2026-08-02", 95.0)
    db.update_settings(user.id, {"target_weight": 80.0})
    assert _reward_rows(db, user.id) == [(10, 98.0), (25, 95.0)]

    db.update_settings(
        user.id,
        {"target_weight": None, "target_bmi": 24.0, "height_cm": 175},
    )
    # Derived target 73.5 -> 10% threshold 97.35; current 95 still inside it.
    assert _reward_rows(db, user.id) == [(10, 97.35)]


@pytest.mark.asyncio
async def test_settings_unset_target_bmi_revokes_checkpoints(app):
    # Spec: clearing target_bmi with target_weight unset leaves no resolved
    # target -> every active checkpoint is revoked.
    db = app.state.db
    user = make_user(db, "bmi-revoke")
    db.upsert_entry(user.id, "2026-08-01", 100.0)
    db.upsert_entry(user.id, "2026-08-02", 95.0)
    db.update_settings(user.id, {"height_cm": 175.0, "target_bmi": 24.0})
    assert _reward_rows(db, user.id) == [(10, 97.35)]

    db.update_settings(user.id, {"target_bmi": None})
    assert db.list_active_rewards(user.id) == []


@pytest.mark.asyncio
async def test_settings_target_bmi_reconcile_isolated_per_user(app):
    # Spec: A's target_bmi change reconciles only A; B's persisted rewards
    # (percent, threshold, earned_at) remain untouched.
    db = app.state.db
    alice = make_user(db, "alice-reconcile")
    bob = make_user(db, "bob-reconcile")
    for user in (alice, bob):
        db.upsert_entry(user.id, "2026-08-01", 100.0)
        db.upsert_entry(user.id, "2026-08-02", 95.0)
        db.update_settings(user.id, {"target_weight": 80.0})
    bob_rows_before = db.list_active_rewards(bob.id)
    assert _reward_rows(db, alice.id) == [(10, 98.0), (25, 95.0)]

    db.update_settings(
        alice.id,
        {"target_weight": None, "target_bmi": 24.0, "height_cm": 175},
    )
    assert _reward_rows(db, alice.id) == [(10, 97.35)]
    assert db.list_active_rewards(bob.id) == bob_rows_before


@pytest.mark.asyncio
async def test_weight_created_at_uses_local_time(onboarded_client, app, monkeypatch):
    # Fresh date: the fixture already seeded 08-01, and an upsert over it would
    # keep its original created_at (ON CONFLICT updates weight/time only).
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-02 21:30:00")
    res = await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 90.5})
    assert res.json()["created_at"] == "2026-08-02 21:30:00"
    row = app.state.db.get_entry_by_date(_onboarded_user_id(app), "2026-08-02")
    assert row.created_at == "2026-08-02 21:30:00"


@pytest.mark.asyncio
async def test_notification_sent_at_uses_local_time(app, monkeypatch):
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-02 21:30:00")
    user = make_user(app.state.db, "tester")
    app.state.db.mark_notification_sent(user.id, "2026-08-02", "tip")
    with app.state.db._tx() as conn:
        row = conn.execute(
            "SELECT sent_at FROM notifications_sent"
            " WHERE user_id = ? AND date = ? AND type = ?",
            (user.id, "2026-08-02", "tip"),
        ).fetchone()
    assert row["sent_at"] == "2026-08-02 21:30:00"


@pytest.mark.asyncio
async def test_weight_summary_includes_target(onboarded_client):
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 90.5})
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    data = (await onboarded_client.get("/api/weight")).json()
    assert data["summary"]["target_kg"] == 80.0
    assert data["summary"]["remaining_kg"] == 10.5


# ---- 2.1: multi-unit + BMI display data --------------------------------


@pytest.mark.asyncio
async def test_weight_entries_include_display_units(onboarded_client):
    # Spec: each history row derives lb/stone from canonical kg; BMI is "—"
    # (None) until height is configured. The onboarded fixture seeds height, so
    # clear it to hold the "no height yet" contract.
    await onboarded_client.put("/api/settings", json={"height_cm": None})
    res = await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 70.0})
    assert res.status_code == 200  # upserts the fixture's seeded 08-01 entry
    entry = res.json()
    assert entry["weight_kg"] == 70.0
    assert entry["lb"] == pytest.approx(70 * 2.2046226218)
    assert entry["stone"] == 11
    assert entry["stone_lb"] == pytest.approx(70 * 2.2046226218 - 14 * 11)
    assert entry["bmi"] is None

    data = (await onboarded_client.get("/api/weight")).json()
    got = data["entries"][0]
    assert got["lb"] == entry["lb"]
    assert got["stone"] == 11
    assert got["stone_lb"] == entry["stone_lb"]
    assert got["bmi"] is None


@pytest.mark.asyncio
async def test_weight_entry_stone_boundary_round_trip(onboarded_client):
    # Regression: 10 st 0 lb entered through the SPA is stored as
    # 140 * 0.45359237 = 63.502931800000006 kg. The derived stone view must
    # report 10 st 0.0 lb (not 9 st 13.999...), which displayed as "9 st 14".
    res = await onboarded_client.post(
        "/api/weight", json={"date": "2026-08-08", "weight_kg": 63.502931800000006}
    )
    assert res.status_code == 201
    entry = res.json()
    assert entry["stone"] == 10
    assert entry["stone_lb"] == 0.0
    assert entry["lb"] == pytest.approx(139.9999999969026)


@pytest.mark.asyncio
async def test_weight_entries_bmi_with_height(onboarded_client):
    # Spec: BMI = kg / (height_cm/100)^2, using unrounded values.
    await onboarded_client.put("/api/settings", json={"height_cm": 175})
    res = await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 70.0})
    body = res.json()
    assert body["bmi"] == pytest.approx(70 / 1.75**2)


@pytest.mark.asyncio
async def test_weight_summary_has_display_units(onboarded_client):
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0, "height_cm": 175})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 90.0})
    summary = (await onboarded_client.get("/api/weight")).json()["summary"]

    # Canonical kg keys stay; multi-unit siblings are raw derived values.
    assert summary["baseline_kg"] == 100.0
    assert summary["baseline_lb"] == pytest.approx(100 * 2.2046226218)
    assert summary["baseline_stone"] == 15
    assert summary["baseline_stone_lb"] == pytest.approx(100 * 2.2046226218 - 14 * 15)
    assert summary["baseline_bmi"] == pytest.approx(100 / 1.75**2)

    assert summary["current_kg"] == 90.0
    assert summary["current_lb"] == pytest.approx(90 * 2.2046226218)
    assert summary["current_stone"] == 14
    assert summary["current_stone_lb"] == pytest.approx(90 * 2.2046226218 - 14 * 14)
    assert summary["current_bmi"] == pytest.approx(90 / 1.75**2)

    assert summary["lost_kg"] == 10.0
    assert summary["lost_lb"] == pytest.approx(10 * 2.2046226218)
    assert summary["lost_stone"] == 1
    assert summary["lost_stone_lb"] == pytest.approx(10 * 2.2046226218 - 14 * 1)

    assert summary["target_kg"] == 80.0
    assert summary["target_lb"] == pytest.approx(80 * 2.2046226218)
    assert summary["target_stone"] == 12
    assert summary["target_stone_lb"] == pytest.approx(80 * 2.2046226218 - 14 * 12)
    assert summary["target_bmi"] == pytest.approx(80 / 1.75**2)

    assert summary["remaining_kg"] == 10.0
    assert summary["remaining_lb"] == pytest.approx(10 * 2.2046226218)
    assert summary["remaining_stone"] == 1
    assert summary["remaining_stone_lb"] == pytest.approx(10 * 2.2046226218 - 14 * 1)

    # Phase 2 contract: healthy range + target status ride on the summary.
    assert summary["healthy_min_kg"] == 56.7
    assert summary["healthy_max_kg"] == 76.3
    assert summary["target_status"] == "overweight"


@pytest.mark.asyncio
async def test_weight_summary_display_none_without_data(auth_client):
    summary = (await auth_client.get("/api/weight")).json()["summary"]
    for key in ("baseline_lb", "baseline_stone", "baseline_stone_lb", "baseline_bmi",
                "current_lb", "current_stone", "current_stone_lb", "current_bmi",
                "lost_lb", "lost_stone", "lost_stone_lb",
                "target_lb", "target_stone", "target_stone_lb", "target_bmi",
                "remaining_lb", "remaining_stone", "remaining_stone_lb"):
        assert summary[key] is None, key
    # Phase 2: no height/target -> healthy range and status are null too.
    assert summary["healthy_min_kg"] is None
    assert summary["healthy_max_kg"] is None
    assert summary["target_status"] is None


@pytest.mark.asyncio
async def test_rewards_checkpoints_include_threshold_units(onboarded_client):
    await onboarded_client.put("/api/settings", json={"target_weight": 80.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await onboarded_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})

    # Setting height must not disturb reward state, only its serialization.
    await onboarded_client.put("/api/settings", json={"height_cm": 175})
    data = (await onboarded_client.get("/api/rewards")).json()

    first = data["active_checkpoints"][0]
    assert first["percent"] == 10
    assert first["threshold_kg"] == 98.0
    assert first["threshold_lb"] == pytest.approx(98 * 2.2046226218)
    assert first["threshold_stone"] == 15
    assert first["threshold_stone_lb"] == pytest.approx(98 * 2.2046226218 - 14 * 15)
    assert first["earned_at"] is not None

    nxt = data["next_checkpoint"]
    assert nxt == {
        "percent": 50,
        "threshold_kg": 90.0,
        "threshold_lb": pytest.approx(90 * 2.2046226218),
        "threshold_stone": 14,
        "threshold_stone_lb": pytest.approx(90 * 2.2046226218 - 14 * 14),
    }


@pytest.mark.asyncio
async def test_weight_in_rejects_unknown_keys(auth_client):
    res = await auth_client.post(
        "/api/weight",
        json={"date": "2026-08-01", "weight_kg": 90.0, "units": "lb"},
    )
    assert res.status_code == 422

# ---- 2.1: target_bmi settings + summary contract (bmi-goal-setting, weight-tracking) ----


@pytest.mark.asyncio
async def test_settings_target_bmi_roundtrip_clears_target_weight(auth_client):
    # Spec (bmi-goal-setting): saving a BMI target MUST round-trip through GET
    # /api/settings and clear target_weight.
    await auth_client.put("/api/settings", json={"height_cm": 175, "target_weight": 80.0})
    res = await auth_client.put("/api/settings", json={"target_bmi": 22.0})
    assert res.status_code == 200
    body = res.json()
    assert body["target_bmi"] == 22.0
    assert body["target_weight"] is None
    got = (await auth_client.get("/api/settings")).json()
    assert got["target_bmi"] == 22.0
    assert got["target_weight"] is None


@pytest.mark.asyncio
async def test_settings_saving_target_weight_clears_target_bmi(auth_client):
    # Design AD2: saving target_weight clears target_bmi (converse of the
    # spec-mandated BMI->weight clearing) so the two targets cannot diverge.
    res = await auth_client.put("/api/settings", json={"height_cm": 175, "target_bmi": 22.0})
    assert res.status_code == 200, res.text
    assert res.json()["target_bmi"] == 22.0
    res = await auth_client.put("/api/settings", json={"target_weight": 80.0})
    assert res.status_code == 200
    assert res.json()["target_weight"] == 80.0
    got = (await auth_client.get("/api/settings")).json()
    assert got["target_weight"] == 80.0
    assert got["target_bmi"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_bmi", [5.0, 45.0])
async def test_settings_target_bmi_out_of_range_rejected_no_persist(auth_client, bad_bmi):
    # Spec: target_bmi outside (10, 40] MUST return 422 and persist no change.
    await auth_client.put("/api/settings", json={"target_weight": 80.0})
    res = await auth_client.put("/api/settings", json={"target_bmi": bad_bmi})
    assert res.status_code == 422
    got = (await auth_client.get("/api/settings")).json()
    assert got["target_bmi"] is None
    assert got["target_weight"] == 80.0


@pytest.mark.asyncio
async def test_settings_target_bmi_without_height_persists_null_target(auth_client):
    # Spec: storing target_bmi with height unset MUST persist, resolve to a
    # null target, and NOT 422.
    res = await auth_client.put("/api/settings", json={"target_bmi": 22.0})
    assert res.status_code == 200
    got = (await auth_client.get("/api/settings")).json()
    assert got["target_bmi"] == 22.0
    summary = (await auth_client.get("/api/weight")).json()["summary"]
    assert summary["target_kg"] is None
    assert summary["target_bmi"] is None
    assert summary["healthy_min_kg"] is None
    assert summary["healthy_max_kg"] is None
    assert summary["target_status"] is None


@pytest.mark.asyncio
async def test_settings_does_not_expose_summary_derived_keys(auth_client):
    # Contract: GET /api/settings returns the persisted k/v surface only —
    # derived summary keys (healthy range, target_status) live in the
    # /api/weight summary, never in settings.
    await auth_client.put("/api/settings", json={"height_cm": 175, "target_weight": 80.0})
    got = (await auth_client.get("/api/settings")).json()
    for key in ("healthy_min_kg", "healthy_max_kg", "target_status", "target_kg"):
        assert key not in got, key
    assert got["target_bmi"] is None
    assert got["onboarding_complete"] is False


@pytest.mark.asyncio
async def test_summary_contract_height_unset_nulls_healthy_range(auth_client):
    # Spec (weight-tracking): height unset -> healthy_min/max_kg null and
    # target_status null even when a target is persisted.
    await auth_client.put("/api/settings", json={"target_weight": 80.0})
    summary = (await auth_client.get("/api/weight")).json()["summary"]
    assert summary["target_kg"] == 80.0
    assert summary["healthy_min_kg"] is None
    assert summary["healthy_max_kg"] is None
    assert summary["target_status"] is None


@pytest.mark.asyncio
async def test_summary_contract_target_unset_nulls_target_status(auth_client):
    # Spec: height set + no target -> healthy range non-null, target_status null.
    await auth_client.put("/api/settings", json={"height_cm": 175})
    summary = (await auth_client.get("/api/weight")).json()["summary"]
    assert summary["target_kg"] is None
    assert summary["healthy_min_kg"] == 56.7
    assert summary["healthy_max_kg"] == 76.3
    assert summary["target_status"] is None


@pytest.mark.asyncio
async def test_summary_and_rewards_target_agree_in_bmi_mode(auth_client):
    # Spec (weight-tracking): with target_bmi 22 + height 175, summary target_kg
    # and rewards target_kg MUST be identical (both via resolve_target_kg).
    await auth_client.put("/api/settings", json={"height_cm": 175, "target_bmi": 22.0})
    await auth_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await auth_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    summary = (await auth_client.get("/api/weight")).json()["summary"]
    rewards = (await auth_client.get("/api/rewards")).json()
    assert summary["target_kg"] == 67.4
    assert rewards["target_kg"] == summary["target_kg"]
    # 67.4 / 1.75^2 = 22.0 -> healthy band.
    assert summary["target_status"] == "healthy"


@pytest.mark.asyncio
async def test_settings_target_bmi_api_reconciles_rewards(auth_client):
    # Spec (target-progress-rewards): persisting target_bmi via PUT /api/settings
    # clears target_weight (AD2) and recomputes checkpoints before the response.
    await auth_client.put("/api/settings", json={"height_cm": 175})
    await auth_client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await auth_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    await auth_client.put("/api/settings", json={"target_weight": 80.0})
    data = (await auth_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25]

    await auth_client.put("/api/settings", json={"target_bmi": 24.0})
    got = (await auth_client.get("/api/settings")).json()
    assert got["target_bmi"] == 24.0
    assert got["target_weight"] is None
    data = (await auth_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10]
    assert data["active_checkpoints"][0]["threshold_kg"] == 97.35


# ---- daily quests API (r1-quests-xp · S1b) -------------------------------


def _today_str() -> str:
    return date.today().isoformat()


@pytest.mark.asyncio
async def test_quest_crud_and_idempotency(auth_client):
    """GET generates three quests and repeats idempotently; complete is a 200
    no-op on done; skip is terminal; terminal quests refuse completion (409)."""
    first = (await auth_client.get("/api/quests")).json()
    assert len(first["quests"]) == 3
    keys = {q["key"] for q in first["quests"]}
    assert len(keys) == 3  # never duplicate keys within a day
    assert "mood_checkin" in keys  # always assigned
    for q in first["quests"]:
        assert q["date"] == _today_str()
        assert q["status"] == "open"
        assert q["completed_at"] is None
        assert q["source"] == "rules"
        assert q["xp_value"] in (20, 40)
        assert q["difficulty"] in ("small", "normal")
        assert "title" in q and "description" in q and "domain" in q
    assert first["is_today_weigh_in"] in (True, False)
    assert first["can_replace"] is True  # fresh day: cap not reached
    assert first["history"] == []  # no past days yet

    # Idempotent generation: a second GET returns the same rows (same ids).
    second = (await auth_client.get("/api/quests")).json()
    assert [q["id"] for q in second["quests"]] == [q["id"] for q in first["quests"]]

    # Complete an open quest -> done; repeating is a 200 no-op with the same
    # completion timestamp.
    target = first["quests"][0]
    done_resp = await auth_client.post(f"/api/quests/{target['id']}/complete")
    assert done_resp.status_code == 200
    done = done_resp.json()
    assert done["status"] == "done"
    assert done["source"] == "manual"
    assert done["completed_at"] is not None
    again = await auth_client.post(f"/api/quests/{target['id']}/complete")
    assert again.status_code == 200
    assert again.json()["completed_at"] == done["completed_at"]

    # Skip another quest -> terminal, zero XP, no completion timestamp;
    # skipping it again is an idempotent 200.
    skip_target = first["quests"][1]
    skipped = (await auth_client.post(f"/api/quests/{skip_target['id']}/skip")).json()
    assert skipped["status"] == "skipped"
    assert skipped["completed_at"] is None
    assert (await auth_client.post(f"/api/quests/{skip_target['id']}/skip")).status_code == 200

    # Terminal quests refuse completion (409); done quests refuse skip (409).
    assert (
        await auth_client.post(f"/api/quests/{skip_target['id']}/complete")
    ).status_code == 409
    assert (await auth_client.post(f"/api/quests/{target['id']}/skip")).status_code == 409

    # A non-integer quest id fails FastAPI path validation (422).
    assert (await auth_client.post("/api/quests/not-an-int/complete")).status_code == 422


@pytest.mark.asyncio
async def test_quest_replace_flow_and_cap(auth_client):
    """Replace swaps the row for one eligible fresh key (never an assigned or
    previously-used key); the one-per-day cap makes the second replace a 409
    without mutation; the replaced row is terminal."""
    first = (await auth_client.get("/api/quests")).json()
    original_keys = {q["key"] for q in first["quests"]}
    target = first["quests"][0]

    resp = await auth_client.post(f"/api/quests/{target['id']}/replace")
    assert resp.status_code == 200
    replacement = resp.json()
    assert replacement["status"] == "open"
    assert replacement["date"] == _today_str()
    assert replacement["key"] not in original_keys  # excludes assigned keys

    # The replaced row is no longer current; the fresh row takes its place and
    # the day's replacement budget is spent.
    after = (await auth_client.get("/api/quests")).json()
    assert len(after["quests"]) == 3
    assert target["id"] not in {q["id"] for q in after["quests"]}
    assert replacement["id"] in {q["id"] for q in after["quests"]}
    assert after["can_replace"] is False

    # The replaced quest is terminal: completing it is a 409.
    assert (await auth_client.post(f"/api/quests/{target['id']}/complete")).status_code == 409
    # A second replacement attempt the same day is a 409 and mutates nothing.
    another = after["quests"][0]
    second_resp = await auth_client.post(f"/api/quests/{another['id']}/replace")
    assert second_resp.status_code == 409
    still = (await auth_client.get("/api/quests")).json()
    assert len(still["quests"]) == 3
    assert [q["id"] for q in still["quests"]] == [q["id"] for q in after["quests"]]


@pytest.mark.asyncio
async def test_quest_wrong_day_409(app, auth_client):
    """Mutations on a quest that is not today's are 409 (spec: non-today), and
    the past quest surfaces only in the bounded history, never as current."""
    db = app.state.db
    user_id = auth_user_id(app)
    past = date(2026, 8, 1)
    rows = db.insert_quests(
        user_id,
        past.isoformat(),
        quests.generate_quests(
            user_id, past, AppSettings(reminder_weekday=0)
        ),
    )
    target = rows[0]
    assert (
        await auth_client.post(f"/api/quests/{target.id}/complete")
    ).status_code == 409
    assert (
        await auth_client.post(f"/api/quests/{target.id}/skip")
    ).status_code == 409
    assert (
        await auth_client.post(f"/api/quests/{target.id}/replace")
    ).status_code == 409
    # The past quest is not current, but the bounded history surfaces it.
    today = (await auth_client.get("/api/quests")).json()
    assert target.id not in {q["id"] for q in today["quests"]}
    assert target.id in {q["id"] for q in today["history"]}


@pytest.mark.asyncio
async def test_quest_404_isolation(pair):
    """Foreign and missing quest ids are hidden as 404 on every mutation and
    the owner's quest is preserved untouched (spec: foreign quest is hidden)."""
    alice, bob = pair
    alice_quests = (await alice.get("/api/quests")).json()["quests"]
    target = alice_quests[0]
    for action in ("complete", "skip", "replace"):
        resp = await bob.post(f"/api/quests/{target['id']}/{action}")
        assert resp.status_code == 404, action
    assert (await alice.post("/api/quests/999999/complete")).status_code == 404
    # Alice's quest is untouched: same ids, all still open.
    current = (await alice.get("/api/quests")).json()["quests"]
    assert [q["id"] for q in current] == [q["id"] for q in alice_quests]
    assert all(q["status"] == "open" for q in current)


@pytest.mark.asyncio
async def test_quest_auto_detection(auth_client):
    """A same-date weight entry marks its mapped quest done with source
    'detected' on read, and stays done on later reads (spec: entry predates
    quest render)."""
    today = date.today()
    # Make today a weigh-in day so log_weight is assigned.
    await auth_client.put(
        "/api/settings", json={"reminder_weekday": today.weekday()}
    )
    await auth_client.post(
        "/api/weight", json={"date": today.isoformat(), "weight_kg": 80.0}
    )
    data = (await auth_client.get("/api/quests")).json()
    by_key = {q["key"]: q for q in data["quests"]}
    assert data["is_today_weigh_in"] is True
    assert "log_weight" in by_key
    assert by_key["log_weight"]["status"] == "done"
    assert by_key["log_weight"]["source"] == "detected"
    assert by_key["log_weight"]["completed_at"] is not None
    # mood_checkin has no detection until S3a — it stays open.
    assert by_key["mood_checkin"]["status"] == "open"
    # A second GET stays done with the same stamp (reconcile is idempotent).
    again = (await auth_client.get("/api/quests")).json()
    again_by_key = {q["key"]: q for q in again["quests"]}
    assert again_by_key["log_weight"]["status"] == "done"
    assert (
        again_by_key["log_weight"]["completed_at"]
        == by_key["log_weight"]["completed_at"]
    )


@pytest.mark.asyncio
async def test_quest_requires_auth(client):
    """Every quest endpoint is authenticated; unauthenticated calls are 401."""
    assert (await client.get("/api/quests")).status_code == 401
    assert (await client.post("/api/quests/1/complete")).status_code == 401
    assert (await client.post("/api/quests/1/skip")).status_code == 401
    assert (await client.post("/api/quests/1/replace")).status_code == 401


# ---- XP API (r1-quests-xp · S2a) ----------------------------------------


@pytest.mark.asyncio
async def test_xp_api_boundaries(auth_client, app):
    """GET /api/xp derives level/title/progress from done quests only; the
    always-assigned 20-XP mood check-in crossing the 100-XP line moves the
    user from level 1 to level 2 (spec: completion crosses a boundary)."""
    zero = (await auth_client.get("/api/xp")).json()
    assert zero == {
        "level": 1,
        "title": "Sprout",
        "total_xp": 0,
        "xp_into_next": 0,
        "next_level_at": 100,
        "recent_completions": [],
    }
    # The API only completes today's rows, so seed 80 XP from past done quests.
    db = app.state.db
    user_id = auth_user_id(app)
    past = date(2026, 7, 27)
    seeded = db.insert_quests(
        user_id,
        past.isoformat(),
        [
            quests.draft_for_key(key, past)
            for key in ("log_meal", "streak_alive", "mood_checkin", "log_weight")
        ],
    )
    for row in seeded:
        db.update_quest_status(user_id, row.id, "done")
    at_80 = (await auth_client.get("/api/xp")).json()
    assert at_80["total_xp"] == 80
    assert at_80["level"] == 1
    assert at_80["title"] == "Sprout"
    assert at_80["xp_into_next"] == 80
    assert at_80["next_level_at"] == 100
    # Completing today's mood check-in (20 XP) crosses into level 2.
    today = (await auth_client.get("/api/quests")).json()["quests"]
    mood = next(q for q in today if q["key"] == "mood_checkin")
    done_resp = await auth_client.post(f"/api/quests/{mood['id']}/complete")
    assert done_resp.status_code == 200
    assert done_resp.json()["level_up"] == {"from": 1, "to": 2}
    crossed = (await auth_client.get("/api/xp")).json()
    assert crossed["total_xp"] == 100
    assert crossed["level"] == 2
    assert crossed["xp_into_next"] == 0
    assert crossed["next_level_at"] == 250


@pytest.mark.asyncio
async def test_level_up_diff_quiet_on_repeat(auth_client, app):
    """Completing an open quest reports the before/after level diff; the
    idempotent repeat is quiet — level_up null and XP unchanged; a completion
    that does not cross a boundary reports null too (spec: quiet on repeat)."""
    db = app.state.db
    user_id = auth_user_id(app)
    past = date(2026, 7, 27)
    seeded = db.insert_quests(
        user_id,
        past.isoformat(),
        [
            quests.draft_for_key(key, past)
            for key in ("log_meal", "streak_alive", "mood_checkin", "log_weight")
        ],
    )
    for row in seeded:
        db.update_quest_status(user_id, row.id, "done")
    today = (await auth_client.get("/api/quests")).json()["quests"]
    mood = next(q for q in today if q["key"] == "mood_checkin")
    first = (await auth_client.post(f"/api/quests/{mood['id']}/complete")).json()
    assert first["status"] == "done"
    assert first["level_up"] == {"from": 1, "to": 2}
    # Repeat: 200 no-op, no new level-up, XP unchanged.
    again = (await auth_client.post(f"/api/quests/{mood['id']}/complete")).json()
    assert again["level_up"] is None
    assert again["completed_at"] == first["completed_at"]
    assert (await auth_client.get("/api/xp")).json()["total_xp"] == 100
    # A completion that stays inside the level reports null too.
    second_target = next(q for q in today if q["key"] != "mood_checkin")
    no_cross = (
        await auth_client.post(f"/api/quests/{second_target['id']}/complete")
    ).json()
    assert no_cross["level_up"] is None


@pytest.mark.asyncio
async def test_xp_recent_completions_bounded_and_ordered(auth_client, app):
    """recent_completions lists the newest 10 done quests (bounded), newest
    date first, with the entry shape {id, quest_key, title, xp_value,
    completed_at} and real catalogue values."""
    db = app.state.db
    user_id = auth_user_id(app)
    settings = AppSettings(reminder_weekday=0)
    for day in (
        date(2026, 7, 6),
        date(2026, 7, 13),
        date(2026, 7, 20),
        date(2026, 7, 27),
    ):
        rows = db.insert_quests(
            user_id, day.isoformat(), quests.generate_quests(user_id, day, settings)
        )
        for row in rows:
            db.update_quest_status(user_id, row.id, "done")
    data = (await auth_client.get("/api/xp")).json()
    recent = data["recent_completions"]
    assert len(recent) == 10  # 12 done quests bounded to 10
    # Newest date first — generation is deterministic, so the expected key
    # set per date is computable here. The three newest days fit whole; the
    # 10-row bound cuts the oldest day (2026-07-06) to its newest row only —
    # the rotating pick, inserted last and so the highest id on that day.
    for expected_day, slice_ in (
        (date(2026, 7, 27), recent[:3]),
        (date(2026, 7, 20), recent[3:6]),
        (date(2026, 7, 13), recent[6:9]),
    ):
        expected_keys = {
            q.quest_key for q in quests.generate_quests(user_id, expected_day, settings)
        }
        assert {r["quest_key"] for r in slice_} == expected_keys
    oldest_keys = {
        q.quest_key for q in quests.generate_quests(user_id, date(2026, 7, 6), settings)
    }
    assert {r["quest_key"] for r in recent[9:]} == oldest_keys - {
        "mood_checkin",
        "log_weight",
    }
    # Entry shape + real catalogue values, completion timestamp stamped.
    first = recent[0]
    assert set(first) == {"id", "quest_key", "title", "xp_value", "completed_at"}
    assert first["completed_at"] is not None
    by_key = {entry[0]: entry for entry in QUEST_POOL}
    assert first["title"] == by_key[first["quest_key"]][2]
    assert first["xp_value"] == by_key[first["quest_key"]][4]


@pytest.mark.asyncio
async def test_xp_api_isolation(app, pair):
    """Spec: keep users isolated — user A's done quests never surface in user
    B's total or recent completions."""
    alice, bob = pair
    alice_user = app.state.db.get_user_by_username("alice")
    bob_user = app.state.db.get_user_by_username("bob")
    assert alice_user is not None and bob_user is not None
    past = date(2026, 7, 27)
    seeded = app.state.db.insert_quests(
        alice_user.id, past.isoformat(), [quests.draft_for_key("exercise_10", past)]
    )
    app.state.db.update_quest_status(alice_user.id, seeded[0].id, "done")
    alice_xp = (await alice.get("/api/xp")).json()
    bob_xp = (await bob.get("/api/xp")).json()
    assert alice_xp["total_xp"] == 40
    assert len(alice_xp["recent_completions"]) == 1
    assert alice_xp["recent_completions"][0]["quest_key"] == "exercise_10"
    assert bob_xp["total_xp"] == 0
    assert bob_xp["recent_completions"] == []


@pytest.mark.asyncio
async def test_xp_requires_auth(client):
    """GET /api/xp is authenticated; unauthenticated calls are 401."""
    assert (await client.get("/api/xp")).status_code == 401


# ---- momentum API (r1-quests-xp · S2b) ------------------------------------


@pytest.mark.asyncio
async def test_momentum_api_shape_and_auth(client, auth_client):
    """GET /api/momentum is authenticated (401 without a session) and returns
    the exact spec surface: today_tier, successful_days, window_days,
    is_successful_today. A fresh user has no quests today → none, window 21."""
    assert (await client.get("/api/momentum")).status_code == 401
    data = (await auth_client.get("/api/momentum")).json()
    assert data == {
        "today_tier": "none",
        "successful_days": 0,
        "window_days": 21,
        "is_successful_today": False,
    }


@pytest.mark.asyncio
async def test_momentum_api_isolation(app, pair):
    """Spec: keep users isolated — alice's done quests move her today_tier to
    Great Day; bob's assigned-but-open quests resolve to none (zero actions)."""
    alice, bob = pair
    db = app.state.db
    alice_user = db.get_user_by_username("alice")
    bob_user = db.get_user_by_username("bob")
    assert alice_user is not None and bob_user is not None
    today = date.today()
    # Alice completes every assigned quest (Great Day) and logs a meal.
    seeded = db.insert_quests(
        alice_user.id,
        today.isoformat(),
        quests.generate_quests(alice_user.id, today, AppSettings(reminder_weekday=0)),
    )
    for row in seeded:
        db.update_quest_status(alice_user.id, row.id, "done")
    db.insert_meal(alice_user.id, today.isoformat(), 600.0)
    # Bob has quests assigned today but nothing done.
    db.insert_quests(
        bob_user.id,
        today.isoformat(),
        quests.generate_quests(bob_user.id, today, AppSettings(reminder_weekday=0)),
    )
    alice_data = (await alice.get("/api/momentum")).json()
    bob_data = (await bob.get("/api/momentum")).json()
    assert alice_data["today_tier"] == "Great Day"
    assert alice_data["is_successful_today"] is True
    assert alice_data["successful_days"] == 1
    assert alice_data["window_days"] == 21
    assert bob_data["today_tier"] == "none"
    assert bob_data["is_successful_today"] is False
    assert bob_data["successful_days"] == 0
    assert bob_data["window_days"] == 21


# ---- achievements API (r2-achievements · S2) -----------------------------


@pytest.mark.asyncio
async def test_achievements_api_requires_auth(client):
    """GET /api/achievements is authenticated; unauthenticated calls are 401
    (spec: isolated API response; threat-matrix HTTP boundary)."""
    assert (await client.get("/api/achievements")).status_code == 401


@pytest.mark.asyncio
async def test_achievements_api_empty_history(auth_client):
    """Spec: empty history — all six states appear in catalogue order, locked
    with null dates, and the entry shape is exactly {key, title, earned,
    unlocked_at}."""
    data = (await auth_client.get("/api/achievements")).json()
    assert data == {
        "achievements": [
            {"key": "getting_started", "title": "Getting Started", "earned": False, "unlocked_at": None},
            {"key": "moving_forward", "title": "Moving Forward", "earned": False, "unlocked_at": None},
            {"key": "consistency", "title": "Consistency", "earned": False, "unlocked_at": None},
            {"key": "comeback", "title": "Comeback", "earned": False, "unlocked_at": None},
            {"key": "explorer", "title": "Explorer", "earned": False, "unlocked_at": None},
            {"key": "personal_best", "title": "Personal Best", "earned": False, "unlocked_at": None},
        ]
    }


@pytest.mark.asyncio
async def test_achievements_api_quest_dates_and_order(auth_client, app):
    """Spec: quest thresholds/dates — earning history surfaces the earliest
    qualifying dates: first done quest (Getting Started), tenth exercise_10
    (Moving Forward), fifth success in the earliest seven-date span
    (Consistency), fifth first-seen domain (Explorer), and the first positive
    exercise day (Personal Best). Comeback stays locked (no inactive run). The
    six states keep catalogue order with the exact entry shape."""
    db = app.state.db
    user_id = auth_user_id(app)
    # 07-01..07-05: five done quests across five distinct domains, each also a
    # successful momentum day (assigned + done → Great Day).
    for day, key in [
        (date(2026, 7, 1), "exercise_10"),
        (date(2026, 7, 2), "log_meal"),
        (date(2026, 7, 3), "streak_alive"),
        (date(2026, 7, 4), "habit_checkin"),
        (date(2026, 7, 5), "mood_checkin"),
    ]:
        seeded = db.insert_quests(
            user_id, day.isoformat(), [quests.draft_for_key(key, day)]
        )
        db.update_quest_status(user_id, seeded[0].id, "done")
    # 07-06..07-14: nine more done exercise_10 quests → the tenth overall lands
    # on 07-14 (Moving Forward).
    for d in range(6, 15):
        day = date(2026, 7, d)
        seeded = db.insert_quests(
            user_id, day.isoformat(), [quests.draft_for_key("exercise_10", day)]
        )
        db.update_quest_status(user_id, seeded[0].id, "done")
    # Exercise rows: 07-01 30 min and 07-02 45 min → Personal Best on 07-01
    # (first positive day, zero baseline).
    db.insert_exercise(user_id, "2026-07-01", "walk", 30)
    db.insert_exercise(user_id, "2026-07-02", "run", 45)

    data = (await auth_client.get("/api/achievements")).json()
    assert [s["key"] for s in data["achievements"]] == [
        "getting_started",
        "moving_forward",
        "consistency",
        "comeback",
        "explorer",
        "personal_best",
    ]
    by_key = {s["key"]: s for s in data["achievements"]}
    assert set(by_key["getting_started"]) == {"key", "title", "earned", "unlocked_at"}
    assert by_key["getting_started"] == {
        "key": "getting_started",
        "title": "Getting Started",
        "earned": True,
        "unlocked_at": "2026-07-01",
    }
    assert by_key["moving_forward"]["unlocked_at"] == "2026-07-14"
    assert by_key["consistency"]["unlocked_at"] == "2026-07-05"
    assert by_key["comeback"]["earned"] is False
    assert by_key["comeback"]["unlocked_at"] is None
    assert by_key["explorer"]["unlocked_at"] == "2026-07-05"
    assert by_key["personal_best"]["unlocked_at"] == "2026-07-01"


@pytest.mark.asyncio
async def test_achievements_api_two_user_isolation(app, pair):
    """Spec: isolated API response — alice's done quests surface in her own six
    states; bob's response stays fully locked (empty history)."""
    alice, bob = pair
    db = app.state.db
    alice_user = db.get_user_by_username("alice")
    bob_user = db.get_user_by_username("bob")
    assert alice_user is not None and bob_user is not None
    day = date(2026, 7, 1)
    seeded = db.insert_quests(
        alice_user.id, day.isoformat(), [quests.draft_for_key("exercise_10", day)]
    )
    db.update_quest_status(alice_user.id, seeded[0].id, "done")

    alice_data = (await alice.get("/api/achievements")).json()
    bob_data = (await bob.get("/api/achievements")).json()
    alice_by_key = {s["key"]: s for s in alice_data["achievements"]}
    assert alice_by_key["getting_started"]["earned"] is True
    assert alice_by_key["getting_started"]["unlocked_at"] == "2026-07-01"
    assert all(not s["earned"] for s in bob_data["achievements"])
    assert all(s["unlocked_at"] is None for s in bob_data["achievements"])


@pytest.mark.asyncio
async def test_achievements_api_gather_isolation_per_user_sums(app, pair):
    """Spec: per-user daily sums (gather isolation) — alice's exercise minutes
    never feed bob's Personal Best; bob's own rows do. Cross-user quests are
    likewise invisible to the gather (alice's done quest never unlocks bob's
    Getting Started)."""
    alice, bob = pair
    db = app.state.db
    alice_user = db.get_user_by_username("alice")
    bob_user = db.get_user_by_username("bob")
    assert alice_user is not None and bob_user is not None
    db.insert_exercise(alice_user.id, "2026-07-01", "walk", 30)
    # Bob logs more minutes on a later date: without user_id filtering his
    # Personal Best would wrongly unlock on alice's earlier day.
    db.insert_exercise(bob_user.id, "2026-07-02", "run", 45)

    alice_data = (await alice.get("/api/achievements")).json()
    bob_data = (await bob.get("/api/achievements")).json()
    alice_by_key = {s["key"]: s for s in alice_data["achievements"]}
    bob_by_key = {s["key"]: s for s in bob_data["achievements"]}
    assert alice_by_key["personal_best"]["unlocked_at"] == "2026-07-01"
    assert bob_by_key["personal_best"]["unlocked_at"] == "2026-07-02"
    assert alice_by_key["getting_started"]["earned"] is False
    assert bob_by_key["getting_started"]["earned"] is False


# ---- weekly objectives API (r2-completion · S2) ----------------------------


@pytest.mark.asyncio
async def test_weekly_first_read_stamps_activation(auth_client, app, monkeypatch):
    """R7: the first weekly read persists the activation stamp; later reads
    keep the original stamp (first read wins, exactly once)."""
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-05 09:00:00")
    data = (await auth_client.get("/api/weekly")).json()
    assert data["activation"] == "2026-08-05 09:00:00"
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-09 09:00:00")
    again = (await auth_client.get("/api/weekly")).json()
    assert again["activation"] == "2026-08-05 09:00:00"


@pytest.mark.asyncio
async def test_weekly_met_flip_once_and_no_double_pay(auth_client, app):
    """R6: a week with 10 done quests and 3 good days pays both 40-XP awards
    (at most 80/week) exactly once; repeat reads emit no new met flips and add
    no XP (reconciliation is idempotent)."""
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(date.today())
    prev = monday - timedelta(days=7)
    # Activation on the previous Monday: the previous week is the first counted
    # week (fully in the past, so the test is weekday-independent).
    db.stamp_weekly_activation(user_id, f"{prev.isoformat()} 09:00:00")
    seed_met_week(db, user_id, prev)
    xp_before = db.total_xp_for_user(user_id)
    first = (await auth_client.get("/api/weekly")).json()
    assert first["met_flips"] == ["quests", "good_days"]
    assert db.total_xp_for_user(user_id) == xp_before + 80
    with db._tx() as conn:
        rows = conn.execute(
            "SELECT goal FROM weekly_awards WHERE user_id = ? ORDER BY goal",
            (user_id,),
        ).fetchall()
    assert [row["goal"] for row in rows] == ["good_days", "quests"]
    # Repeated reads stay quiet: no flips, no new XP, no new rows.
    second = (await auth_client.get("/api/weekly")).json()
    assert second["met_flips"] == []
    assert db.total_xp_for_user(user_id) == xp_before + 80
    # The paid week appears in history as met and awarded; the current week is
    # counted but neither met nor paid.
    history = {h["week_start"]: h for h in second["history"]}
    paid = history[prev.isoformat()]
    assert paid["exempt"] is False
    paid_goals = {g["goal"]: g for g in paid["goals"]}
    assert paid_goals["quests"]["met"] is True
    assert paid_goals["quests"]["awarded"] is True
    assert paid_goals["good_days"]["met"] is True
    assert paid_goals["good_days"]["awarded"] is True
    assert second["current"]["exempt"] is False
    current_goals = {g["goal"]: g for g in second["current"]["goals"]}
    assert current_goals["quests"]["met"] is False
    assert current_goals["quests"]["awarded"] is False


@pytest.mark.asyncio
async def test_weekly_tenth_quest_pays_immediately(auth_client, app, monkeypatch):
    """R6 scenario: an eligible week at 9 done quests pays +40 the moment the
    tenth quest becomes done — the very next /api/xp read, with no /api/weekly
    in between, already includes the award. Exactly once: one award row, no
    double pay, and the next weekly read reports the goal met+awarded with no
    new flip (payment happened up front)."""
    fixed = date(2026, 8, 5)  # Wednesday; week starts Mon 2026-08-03

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(database_module, "date", _FixedDate)
    monkeypatch.setattr(routes_module, "date", _FixedDate)
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-05 09:00:00")
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(fixed)
    # Activation on the week's Monday: the current week is the first counted one.
    db.stamp_weekly_activation(user_id, f"{monday.isoformat()} 09:00:00")
    mark_done(db, user_id, monday, [entry[0] for entry in QUEST_POOL])
    mark_done(
        db,
        user_id,
        monday + timedelta(days=1),
        ["exercise_10", "log_meal", "streak_alive"],
    )
    xp_before = db.total_xp_for_user(user_id)
    # The tenth quest becomes done through the API today.
    today_quests = (await auth_client.get("/api/quests")).json()["quests"]
    target = today_quests[0]
    assert (
        await auth_client.post(f"/api/quests/{target['id']}/complete")
    ).status_code == 200
    # IMMEDIATE transition: the sequential /api/xp read (SPA contract) already
    # shows quest XP plus the 40-XP award — no /api/weekly read in between.
    xp = (await auth_client.get("/api/xp")).json()
    assert xp["total_xp"] == xp_before + target["xp_value"] + 40
    # The award row was persisted at completion: one row, exactly once.
    with db._tx() as conn:
        rows = conn.execute(
            "SELECT goal, xp_awarded FROM weekly_awards WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    assert [(row["goal"], row["xp_awarded"]) for row in rows] == [("quests", 40)]
    # The next weekly read reports the goal as met and awarded with no new
    # flip: the payment happened up front, so the read has nothing to pay.
    post = (await auth_client.get("/api/weekly")).json()
    assert post["met_flips"] == []
    quests_goal = next(g for g in post["current"]["goals"] if g["goal"] == "quests")
    assert quests_goal["met"] is True and quests_goal["awarded"] is True


@pytest.mark.asyncio
async def test_weekly_non_tenth_completion_pays_no_award(auth_client, app, monkeypatch):
    """R6 triangulation: completing a NON-tenth quest (the week's first) adds
    only that quest's XP — the quests objective (1 / 10) is not met, so no
    weekly award is paid."""
    fixed = date(2026, 8, 5)  # Wednesday; week starts Mon 2026-08-03

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(database_module, "date", _FixedDate)
    monkeypatch.setattr(routes_module, "date", _FixedDate)
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-05 09:00:00")
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(fixed)
    db.stamp_weekly_activation(user_id, f"{monday.isoformat()} 09:00:00")
    mark_done(db, user_id, monday, ["log_meal"])  # one done quest: 1 / 10
    xp_before = db.total_xp_for_user(user_id)
    today_quests = (await auth_client.get("/api/quests")).json()["quests"]
    target = today_quests[0]
    assert (
        await auth_client.post(f"/api/quests/{target['id']}/complete")
    ).status_code == 200
    # Only the quest's own XP: the objective is still unmet, so no +40.
    xp = (await auth_client.get("/api/xp")).json()
    assert xp["total_xp"] == xp_before + target["xp_value"]
    with db._tx() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM weekly_awards WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    assert count == 0


@pytest.mark.asyncio
async def test_weekly_detected_tenth_quest_pays_during_quest_read(
    auth_client, app, monkeypatch
):
    """R6 detection path: a read-detected tenth completion pays the weekly
    awards during that same GET /api/quests — the sequential /api/xp read
    (SPA contract) shows them with no /api/weekly read in between."""
    fixed = date(2026, 8, 5)  # Wednesday; week starts Mon 2026-08-03

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(database_module, "date", _FixedDate)
    monkeypatch.setattr(routes_module, "date", _FixedDate)
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-05 09:00:00")
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(fixed)
    db.stamp_weekly_activation(user_id, f"{monday.isoformat()} 09:00:00")
    mark_done(db, user_id, monday, [entry[0] for entry in QUEST_POOL])
    mark_done(
        db,
        user_id,
        monday + timedelta(days=1),
        ["exercise_10", "log_meal", "streak_alive"],
    )
    xp_before = db.total_xp_for_user(user_id)
    # First read generates today's quests with no facts: plain read, nothing
    # detected, nothing paid.
    first = (await auth_client.get("/api/quests")).json()["quests"]
    mood = next(q for q in first if q["key"] == "mood_checkin")
    assert mood["status"] == "open"
    # A mood check-in today proves mood_checkin done: the next quest read
    # detects it (source 'detected') and must pay the awards in that request.
    resp = await auth_client.post(
        "/api/mood", json={"mood": 4, "date": fixed.isoformat()}
    )
    assert resp.status_code == 201
    second = (await auth_client.get("/api/quests")).json()["quests"]
    mood_done = next(q for q in second if q["key"] == "mood_checkin")
    assert mood_done["status"] == "done"
    assert mood_done["source"] == "detected"
    # IMMEDIATE payment: 10 done quests pay the quests award AND the mood log
    # row makes Wednesday a Good day, so good_days (3) pays too — both paid
    # during the quest read, visible on the immediate /api/xp read.
    xp = (await auth_client.get("/api/xp")).json()
    assert xp["total_xp"] == xp_before + mood_done["xp_value"] + 80


@pytest.mark.asyncio
async def test_weekly_mutation_award_exactly_once(auth_client, app, monkeypatch):
    """R6 exactly-once on the mutation path: repeating the completion
    (idempotent 200) and repeating the weekly read never double-pay — one
    40-XP quests row at most (≤80/week), and the objective's awarded state
    flips true exactly once."""
    fixed = date(2026, 8, 5)  # Wednesday; week starts Mon 2026-08-03

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(database_module, "date", _FixedDate)
    monkeypatch.setattr(routes_module, "date", _FixedDate)
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-05 09:00:00")
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(fixed)
    db.stamp_weekly_activation(user_id, f"{monday.isoformat()} 09:00:00")
    mark_done(db, user_id, monday, [entry[0] for entry in QUEST_POOL])
    mark_done(
        db,
        user_id,
        monday + timedelta(days=1),
        ["exercise_10", "log_meal", "streak_alive"],
    )
    xp_before = db.total_xp_for_user(user_id)
    today_quests = (await auth_client.get("/api/quests")).json()["quests"]
    target = today_quests[0]
    first = await auth_client.post(f"/api/quests/{target['id']}/complete")
    assert first.status_code == 200
    assert db.total_xp_for_user(user_id) == xp_before + target["xp_value"] + 40
    # Idempotent repeat: 200 no-op, no second award, no level-up reported.
    again = await auth_client.post(f"/api/quests/{target['id']}/complete")
    assert again.status_code == 200
    assert again.json()["level_up"] is None
    assert db.total_xp_for_user(user_id) == xp_before + target["xp_value"] + 40
    # Repeated weekly reads stay quiet: no new flips, no new XP.
    post = (await auth_client.get("/api/weekly")).json()
    assert post["met_flips"] == []
    assert db.total_xp_for_user(user_id) == xp_before + target["xp_value"] + 40
    again_read = (await auth_client.get("/api/weekly")).json()
    assert again_read["met_flips"] == []
    assert db.total_xp_for_user(user_id) == xp_before + target["xp_value"] + 40
    # Exactly one quests award row (at most 80 XP/week from weekly awards).
    with db._tx() as conn:
        rows = conn.execute(
            "SELECT goal, xp_awarded FROM weekly_awards WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    assert [(row["goal"], row["xp_awarded"]) for row in rows] == [("quests", 40)]


@pytest.mark.asyncio
async def test_weekly_tenth_completion_level_up_includes_award(
    auth_client, app, monkeypatch
):
    """R6 level-up correctness: the +40 award is what pushes the user across
    the level boundary (220 + 20 quest XP = 240 stays level 2; +40 = 280
    crosses into level 3), so complete_quest's level_up must reflect the
    award-inclusive total — without the fix the crossing is missed."""
    fixed = date(2026, 8, 5)  # Wednesday; week starts Mon 2026-08-03

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(database_module, "date", _FixedDate)
    monkeypatch.setattr(routes_module, "date", _FixedDate)
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-05 09:00:00")
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(fixed)
    db.stamp_weekly_activation(user_id, f"{monday.isoformat()} 09:00:00")
    mark_done(db, user_id, monday, [entry[0] for entry in QUEST_POOL])
    mark_done(
        db,
        user_id,
        monday + timedelta(days=1),
        ["exercise_10", "log_meal", "streak_alive"],
    )
    # 9 seeded quests = 220 XP → level 2; the tenth is a 20-XP quest.
    assert db.total_xp_for_user(user_id) == 220
    today_quests = (await auth_client.get("/api/quests")).json()["quests"]
    mood = next(q for q in today_quests if q["key"] == "mood_checkin")
    assert mood["xp_value"] == 20
    body = (await auth_client.post(f"/api/quests/{mood['id']}/complete")).json()
    # Without the +40 the total would be 240 (still level 2); the award makes
    # it 280 → level 3. level_up must report that award-inclusive crossing.
    assert body["level_up"] == {"from": 2, "to": 3}
    xp_state = (await auth_client.get("/api/xp")).json()
    assert xp_state["total_xp"] == 280
    assert xp_state["level"] == 3


@pytest.mark.asyncio
async def test_weekly_activation_independent_between_users(pair, app, monkeypatch):
    """R7 scenario: each user's counted weeks derive only from their own
    activation stamp — a mid-week activation exempts the partial week while an
    earlier Monday activation counts the current week."""
    alice, bob = pair
    db = app.state.db
    monday = weekly.week_start(date.today())
    alice_stamp = (monday + timedelta(days=2)).isoformat() + " 09:00:00"
    bob_stamp = (monday - timedelta(days=7)).isoformat() + " 09:00:00"
    monkeypatch.setattr(database_module, "_local_now", lambda: alice_stamp)
    alice_data = (await alice.get("/api/weekly")).json()
    monkeypatch.setattr(database_module, "_local_now", lambda: bob_stamp)
    bob_data = (await bob.get("/api/weekly")).json()
    assert alice_data["activation"] == alice_stamp
    assert bob_data["activation"] == bob_stamp
    assert alice_data["current"]["exempt"] is True  # partial activation week
    assert bob_data["current"]["exempt"] is False  # counted from last Monday


@pytest.mark.asyncio
async def test_weekly_history_capped_at_twelve(auth_client, app):
    """History is bounded to the newest 12 completed weeks, newest first."""
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(date.today())
    db.stamp_weekly_activation(
        user_id, f"{(monday - timedelta(days=7)).isoformat()} 09:00:00"
    )
    for offset in range(1, 15):  # 14 previous weeks with one done quest each
        day = monday - timedelta(days=7 * offset)
        mark_done(db, user_id, day, ["mood_checkin"])
    data = (await auth_client.get("/api/weekly")).json()
    assert len(data["history"]) == 12
    assert data["history"][0]["week_start"] == (
        monday - timedelta(days=7)
    ).isoformat()
    assert data["history"][-1]["week_start"] == (
        monday - timedelta(days=7 * 12)
    ).isoformat()


def test_weekly_snapshot_gather(tmp_path):
    """weekly_snapshot counts done quests and Good/Great days week-bounded and
    reports the week's already-awarded goals (Spark and out-of-week rows never
    count)."""
    db = database_module.Database(str(tmp_path / "weekly.db"))
    db.init_schema()
    try:
        user = make_user(db, "snapshot-user")
        monday = weekly.week_start(date.today())
        prev = monday - timedelta(days=7)
        seed_met_week(db, user.id, prev)
        # A done quest OUTSIDE the week must not count toward it.
        mark_done(db, user.id, monday, ["mood_checkin"])
        snap = db.weekly_snapshot(user.id, prev)
        assert snap.week == prev.isoformat()
        assert snap.done_quests == 11
        assert snap.good_days == 3  # the Spark day never counts
        assert snap.awarded == set()
        # Week-bounded: the current week's rows are excluded from the past one.
        current = db.weekly_snapshot(user.id, monday)
        assert current.done_quests == 1
        assert current.good_days == 1  # one done quest is a Great Day
        # Already-awarded goals are reported.
        with db._tx() as conn:
            conn.execute(
                "INSERT INTO weekly_awards (user_id, week_start, goal, xp_awarded)"
                " VALUES (?, ?, 'quests', 40)",
                (user.id, prev.isoformat()),
            )
        paid = db.weekly_snapshot(user.id, prev)
        assert paid.awarded == {"quests"}
    finally:
        db.close()


def test_weekly_awards_schema_constraints(tmp_path):
    """weekly_awards enforces its contract at the schema: composite PK
    (user_id, week_start, goal), the goal allowlist, and exactly 40 XP."""
    db = database_module.Database(str(tmp_path / "weekly.db"))
    db.init_schema()
    try:
        user = make_user(db, "schema-user")
        with db._tx() as conn:
            conn.execute(
                "INSERT INTO weekly_awards (user_id, week_start, goal, xp_awarded)"
                " VALUES (?, '2026-08-03', 'quests', 40)",
                (user.id,),
            )
        with pytest.raises(sqlite3.IntegrityError):  # duplicate PK
            with db._tx() as conn:
                conn.execute(
                    "INSERT INTO weekly_awards"
                    " (user_id, week_start, goal, xp_awarded)"
                    " VALUES (?, '2026-08-03', 'quests', 40)",
                    (user.id,),
                )
        with pytest.raises(sqlite3.IntegrityError):  # unknown goal
            with db._tx() as conn:
                conn.execute(
                    "INSERT INTO weekly_awards"
                    " (user_id, week_start, goal, xp_awarded)"
                    " VALUES (?, '2026-08-03', 'streaks', 40)",
                    (user.id,),
                )
        with pytest.raises(sqlite3.IntegrityError):  # wrong award value
            with db._tx() as conn:
                conn.execute(
                    "INSERT INTO weekly_awards"
                    " (user_id, week_start, goal, xp_awarded)"
                    " VALUES (?, '2026-08-03', 'quests', 20)",
                    (user.id,),
                )
    finally:
        db.close()


# ---- collectibles API (r2-completion · S4) ----------------------------------


@pytest.mark.asyncio
async def test_collectibles_shape_and_catalogue_order(auth_client, app):
    """R10/R11: the 16-token shelf returns in catalogue order with the exact
    {key,title,earned,unlocked_at} shape, and the read never changes XP."""
    db = app.state.db
    user_id = auth_user_id(app)
    monday = weekly.week_start(date.today())
    await auth_client.put("/api/settings", json={"target_weight": 80.0, "height_cm": 175.0})
    db.upsert_entry(user_id, (monday - timedelta(days=1)).isoformat(), 100.0)
    db.upsert_entry(user_id, monday.isoformat(), 90.0)
    for offset in range(7):
        db.insert_meal(user_id, (monday + timedelta(days=offset)).isoformat(), 500.0)
    seed_met_week(db, user_id, monday)
    xp_before = db.total_xp_for_user(user_id)
    items = (await auth_client.get("/api/collectibles")).json()["collectibles"]
    assert [i["key"] for i in items] == [k for k, _ in COLLECTIBLE_CATALOG]
    assert [i["title"] for i in items] == [t for _, t in COLLECTIBLE_CATALOG]
    assert all(set(i) == {"key", "title", "earned", "unlocked_at"} for i in items)
    by_key = {i["key"]: i for i in items}
    # Seeded week: first done quest, three checkpoint crosses, 7-day meal run,
    # and both weekly objectives unlock at their seeded dates.
    assert by_key["getting_started"]["unlocked_at"] == monday.isoformat()
    assert by_key["checkpoint_50"]["unlocked_at"] == monday.isoformat()
    assert by_key["meal_7"]["unlocked_at"] == (monday + timedelta(days=6)).isoformat()
    assert by_key["weekly_quests"]["unlocked_at"] == monday.isoformat()
    assert by_key["weekly_good_days"]["unlocked_at"] == monday.isoformat()
    assert all(by_key[k]["earned"] is False and by_key[k]["unlocked_at"] is None for k in ("moving_forward", "checkpoint_75", "meal_30", "meal_100"))
    assert db.total_xp_for_user(user_id) == xp_before  # R10: cosmetic-only read
