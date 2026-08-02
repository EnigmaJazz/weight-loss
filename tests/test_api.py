"""API tests: weight summary, settings roundtrip, push endpoints, rewards."""

import pytest

import database as database_module

SUBSCRIBE_BODY = {
    "endpoint": "https://push.example.com/v1/abcd1234",
    "p256dh": "BEl62iUYgUivxIkv69yViEuiBIa_IbT8n1sWj3N5nPw",
    "auth": "F8UVa5fTzFQXlq6dZ0Gt7g",
}


@pytest.mark.asyncio
async def test_weight_empty(client):
    data = (await client.get("/api/weight")).json()
    assert data["entries"] == []
    assert data["summary"]["baseline_kg"] is None
    assert data["summary"]["current_kg"] is None
    assert data["summary"]["lost_kg"] is None


@pytest.mark.asyncio
async def test_settings_get_returns_defaults(client):
    data = (await client.get("/api/settings")).json()
    assert "milestone_step_kg" not in data
    assert data["height_cm"] is None
    assert data["tip_time"] == "09:00"
    assert data["reminder_time"] == "20:00"
    assert data["exercise_time"] == "17:00"
    assert data["target_weight"] is None
    assert data["start_weight_override"] is None


@pytest.mark.asyncio
async def test_settings_put_partial_update(client):
    res = await client.put("/api/settings", json={"target_weight": 80.0})
    assert res.status_code == 200
    body = res.json()
    assert body["target_weight"] == 80.0
    assert body["height_cm"] is None

    got = (await client.get("/api/settings")).json()
    assert got["target_weight"] == 80.0


@pytest.mark.asyncio
async def test_settings_clear_override_with_null(client):
    await client.put("/api/settings", json={"target_weight": 80.0})
    await client.put("/api/settings", json={"target_weight": None})
    got = (await client.get("/api/settings")).json()
    assert got["target_weight"] is None


@pytest.mark.asyncio
async def test_settings_bad_time_rejected(client):
    res = await client.put("/api/settings", json={"tip_time": "25:99"})
    assert res.status_code == 422
    res = await client.put("/api/settings", json={"reminder_time": "not-a-time"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_settings_retired_key_rejected(client):
    # Spec: the retired milestone_step_kg setting must be rejected and must not
    # change the stored settings.
    await client.put("/api/settings", json={"target_weight": 80.0})
    res = await client.put("/api/settings", json={"milestone_step_kg": 2.0})
    assert res.status_code == 422
    got = (await client.get("/api/settings")).json()
    assert got["target_weight"] == 80.0
    assert "milestone_step_kg" not in got


@pytest.mark.asyncio
async def test_settings_save_height(client):
    res = await client.put("/api/settings", json={"height_cm": 175})
    assert res.status_code == 200
    assert res.json()["height_cm"] == 175
    got = (await client.get("/api/settings")).json()
    assert got["height_cm"] == 175


@pytest.mark.asyncio
async def test_settings_nonpositive_height_rejected(client):
    res = await client.put("/api/settings", json={"height_cm": 0})
    assert res.status_code == 422
    res = await client.put("/api/settings", json={"height_cm": -5})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_vapid_public_key(client):
    data = (await client.get("/api/push/vapid-public-key")).json()
    assert "public_key" in data
    assert len(data["public_key"]) > 20


@pytest.mark.asyncio
async def test_push_subscribe_bad_endpoint_rejected(client):
    bad = {**SUBSCRIBE_BODY, "endpoint": "not-a-url"}
    res = await client.post("/api/push/subscribe", json=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_push_subscribe_unsubscribe(client, app):
    res = await client.post("/api/push/subscribe", json=SUBSCRIBE_BODY)
    assert res.status_code == 201
    subs = app.state.db.list_subscriptions()
    assert len(subs) == 1
    assert subs[0].endpoint == SUBSCRIBE_BODY["endpoint"]

    res = await client.post(
        "/api/push/unsubscribe", json={"endpoint": SUBSCRIBE_BODY["endpoint"]}
    )
    assert res.status_code == 200
    assert res.json() == {"removed": True}
    assert app.state.db.list_subscriptions() == []


@pytest.mark.asyncio
async def test_push_test_sends_to_all(client, stub_push):
    await client.post("/api/push/subscribe", json=SUBSCRIBE_BODY)
    res = await client.post("/api/push/test")
    assert res.status_code == 200
    body = res.json()
    assert body == {"sent": 1, "total": 1}
    assert len(stub_push) == 1
    assert "Test notification" in stub_push[0]["body"]


@pytest.mark.asyncio
async def test_manual_notify_endpoints(client, stub_push):
    await client.post("/api/push/subscribe", json=SUBSCRIBE_BODY)
    for notif_type in ("tip", "reminder", "exercise"):
        res = await client.post(f"/api/notify/{notif_type}")
        assert res.status_code == 200
        assert res.json() == {"sent": 1, "total": 1}
    assert len(stub_push) == 3

    res = await client.post("/api/notify/bogus")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_rewards_empty(client):
    data = (await client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []
    assert data["earned_count"] == 0
    assert data["next_checkpoint"] is None
    assert data["progress_to_next"] == 0.0


@pytest.mark.asyncio
async def test_rewards_checkpoints_earned_via_upserts(client):
    await client.put("/api/settings", json={"target_weight": 80.0})
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    data = (await client.get("/api/rewards")).json()
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
async def test_rewards_regression_revokes_checkpoints(client):
    await client.put("/api/settings", json={"target_weight": 80.0})
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    await client.post("/api/weight", json={"date": "2026-08-03", "weight_kg": 99.0})
    data = (await client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []
    assert data["earned_count"] == 0
    nxt = data["next_checkpoint"]
    assert nxt["percent"] == 10
    assert nxt["threshold_kg"] == 98.0
    assert nxt["threshold_lb"] == pytest.approx(98 * 2.2046226218)
    assert nxt["threshold_stone"] == 15
    assert nxt["threshold_stone_lb"] == pytest.approx(98 * 2.2046226218 - 14 * 15)


@pytest.mark.asyncio
async def test_rewards_reenroll_refreshes_earned_at(client, app, monkeypatch):
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-02 09:00:00")
    await client.put("/api/settings", json={"target_weight": 80.0})
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    rows = app.state.db.list_active_rewards()
    assert {r["checkpoint_percent"] for r in rows} == {10, 25}
    assert all(r["earned_at"] == "2026-08-02 09:00:00" for r in rows)

    # Regression revokes every checkpoint.
    await client.post("/api/weight", json={"date": "2026-08-03", "weight_kg": 99.0})
    assert app.state.db.list_active_rewards() == []

    # Renewed progress re-earns with a NEW local timestamp.
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-04 18:30:00")
    await client.post("/api/weight", json={"date": "2026-08-04", "weight_kg": 90.0})
    rows = app.state.db.list_active_rewards()
    assert {r["checkpoint_percent"] for r in rows} == {10, 25, 50}
    assert all(r["earned_at"] == "2026-08-04 18:30:00" for r in rows)


@pytest.mark.asyncio
async def test_rewards_historical_upsert_changes_start(client):
    await client.put("/api/settings", json={"target_weight": 80.0})
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    data = (await client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []

    # An earlier-dated entry moves the start (and thresholds) back to 100.
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    data = (await client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25]


@pytest.mark.asyncio
async def test_rewards_delete_reconciles(client, app):
    await client.put("/api/settings", json={"target_weight": 80.0})
    created = (await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})).json()
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    assert len(app.state.db.list_active_rewards()) == 2

    await client.delete(f"/api/weight/{created['id']}")
    data = (await client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []
    assert app.state.db.list_active_rewards() == []


@pytest.mark.asyncio
async def test_settings_update_reconciles_rewards(client):
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})
    data = (await client.get("/api/rewards")).json()
    assert data["active_checkpoints"] == []

    # Setting a target triggers reconciliation.
    await client.put("/api/settings", json={"target_weight": 80.0})
    data = (await client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25]

    # Moving the override (start 100 -> 110) re-derives thresholds.
    await client.put("/api/settings", json={"start_weight_override": 110.0})
    data = (await client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in data["active_checkpoints"]] == [10, 25, 50]


@pytest.mark.asyncio
async def test_weight_created_at_uses_local_time(client, app, monkeypatch):
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-02 21:30:00")
    res = await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 90.5})
    assert res.json()["created_at"] == "2026-08-02 21:30:00"
    row = app.state.db.get_entry_by_date("2026-08-01")
    assert row.created_at == "2026-08-02 21:30:00"


@pytest.mark.asyncio
async def test_notification_sent_at_uses_local_time(app, monkeypatch):
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-02 21:30:00")
    app.state.db.mark_notification_sent("2026-08-02", "tip")
    with app.state.db._tx() as conn:
        row = conn.execute(
            "SELECT sent_at FROM notifications_sent WHERE date = ? AND type = ?",
            ("2026-08-02", "tip"),
        ).fetchone()
    assert row["sent_at"] == "2026-08-02 21:30:00"


@pytest.mark.asyncio
async def test_weight_summary_includes_target(client):
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 90.5})
    await client.put("/api/settings", json={"target_weight": 80.0})
    data = (await client.get("/api/weight")).json()
    assert data["summary"]["target_kg"] == 80.0
    assert data["summary"]["remaining_kg"] == 10.5


# ---- 2.1: multi-unit + BMI display data --------------------------------


@pytest.mark.asyncio
async def test_weight_entries_include_display_units(client):
    # Spec: each history row derives lb/stone from canonical kg; BMI is "—"
    # (None) until height is configured.
    res = await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 70.0})
    assert res.status_code == 201
    entry = res.json()
    assert entry["weight_kg"] == 70.0
    assert entry["lb"] == pytest.approx(70 * 2.2046226218)
    assert entry["stone"] == 11
    assert entry["stone_lb"] == pytest.approx(70 * 2.2046226218 - 14 * 11)
    assert entry["bmi"] is None

    data = (await client.get("/api/weight")).json()
    got = data["entries"][0]
    assert got["lb"] == entry["lb"]
    assert got["stone"] == 11
    assert got["stone_lb"] == entry["stone_lb"]
    assert got["bmi"] is None


@pytest.mark.asyncio
async def test_weight_entries_bmi_with_height(client):
    # Spec: BMI = kg / (height_cm/100)^2, using unrounded values.
    await client.put("/api/settings", json={"height_cm": 175})
    res = await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 70.0})
    body = res.json()
    assert body["bmi"] == pytest.approx(70 / 1.75**2)


@pytest.mark.asyncio
async def test_weight_summary_has_display_units(client):
    await client.put("/api/settings", json={"target_weight": 80.0, "height_cm": 175})
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 90.0})
    summary = (await client.get("/api/weight")).json()["summary"]

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


@pytest.mark.asyncio
async def test_weight_summary_display_none_without_data(client):
    summary = (await client.get("/api/weight")).json()["summary"]
    for key in ("baseline_lb", "baseline_stone", "baseline_stone_lb", "baseline_bmi",
                "current_lb", "current_stone", "current_stone_lb", "current_bmi",
                "lost_lb", "lost_stone", "lost_stone_lb",
                "target_lb", "target_stone", "target_stone_lb", "target_bmi",
                "remaining_lb", "remaining_stone", "remaining_stone_lb"):
        assert summary[key] is None, key


@pytest.mark.asyncio
async def test_rewards_checkpoints_include_threshold_units(client):
    await client.put("/api/settings", json={"target_weight": 80.0})
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 100.0})
    await client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 95.0})

    # Setting height must not disturb reward state, only its serialization.
    await client.put("/api/settings", json={"height_cm": 175})
    data = (await client.get("/api/rewards")).json()

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
async def test_weight_in_rejects_unknown_keys(client):
    res = await client.post(
        "/api/weight",
        json={"date": "2026-08-01", "weight_kg": 90.0, "units": "lb"},
    )
    assert res.status_code == 422
