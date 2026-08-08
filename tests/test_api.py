"""API tests: weight summary, settings roundtrip, push endpoints, rewards."""

import pytest
from fastapi import FastAPI

import database as database_module
from tests.conftest import ONBOARDED_USERNAME, auth_user_id, make_user, pair

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
