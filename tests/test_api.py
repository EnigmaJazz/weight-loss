"""API tests: weight summary, settings roundtrip, push endpoints, rewards."""

import pytest

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
    assert data["milestone_step_kg"] == 1.0
    assert data["tip_time"] == "09:00"
    assert data["reminder_time"] == "20:00"
    assert data["exercise_time"] == "17:00"
    assert data["target_weight"] is None


@pytest.mark.asyncio
async def test_settings_put_partial_update(client):
    res = await client.put("/api/settings", json={"target_weight": 80.0})
    assert res.status_code == 200
    body = res.json()
    assert body["target_weight"] == 80.0
    assert body["milestone_step_kg"] == 1.0

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
async def test_settings_bad_step_rejected(client):
    res = await client.put("/api/settings", json={"milestone_step_kg": 0})
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
    assert data["earned_count"] == 0
    assert data["reward_total_kg"] == 0.0


@pytest.mark.asyncio
async def test_rewards_earns_milestone(client):
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 90.5})
    data = (await client.get("/api/rewards")).json()
    assert data["earned_count"] == 0
    assert data["next_milestone_kg"] == 1.0

    await client.post("/api/weight", json={"date": "2026-08-03", "weight_kg": 89.2})
    data = (await client.get("/api/rewards")).json()
    assert data["earned_count"] == 1
    assert data["reward_total_kg"] == 1.0
    assert data["next_milestone_kg"] == 2.0
    assert data["progress_to_next"] == 0.3
    earned = [m for m in data["milestones"] if m["earned"]]
    assert earned[0]["milestone_kg"] == 1.0
    assert earned[0]["earned_at"] is not None


@pytest.mark.asyncio
async def test_weight_summary_includes_target(client):
    await client.post("/api/weight", json={"date": "2026-08-01", "weight_kg": 90.5})
    await client.put("/api/settings", json={"target_weight": 80.0})
    data = (await client.get("/api/weight")).json()
    assert data["summary"]["target_kg"] == 80.0
    assert data["summary"]["remaining_kg"] == 10.5
