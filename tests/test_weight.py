"""API tests for weight logging: add, update-on-duplicate, delete, validation."""

import pytest

from database import Database
from main import create_app, init_app_state


def _post(auth_client, date, weight_kg):
    return auth_client.post(
        "/api/weight",
        json={"date": date, "weight_kg": weight_kg},
    )


@pytest.mark.asyncio
async def test_add_entry(auth_client):
    res = await _post(auth_client, "2026-08-01", 90.5)
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-08-01"
    assert body["weight_kg"] == 90.5

    got = await auth_client.get("/api/weight")
    data = got.json()
    assert len(data["entries"]) == 1
    assert data["summary"]["baseline_kg"] == 90.5
    assert data["summary"]["current_kg"] == 90.5
    assert data["summary"]["lost_kg"] == 0.0


@pytest.mark.asyncio
async def test_update_on_duplicate_date(auth_client):
    await _post(auth_client, "2026-08-01", 90.5)
    res = await _post(auth_client, "2026-08-01", 88.0)
    assert res.status_code == 200
    assert res.json()["weight_kg"] == 88.0

    data = (await auth_client.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["weight_kg"] == 88.0


@pytest.mark.asyncio
async def test_delete_entry(auth_client):
    created = (await _post(auth_client, "2026-08-01", 90.5)).json()
    res = await auth_client.delete(f"/api/weight/{created['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}

    data = (await auth_client.get("/api/weight")).json()
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_delete_missing_entry_404(auth_client):
    res = await auth_client.delete("/api/weight/9999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_negative_weight_rejected(auth_client):
    res = await _post(auth_client, "2026-08-01", -5.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_zero_weight_rejected(auth_client):
    res = await _post(auth_client, "2026-08-01", 0.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_bad_date_rejected(auth_client):
    res = await _post(auth_client, "not-a-date", 85.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_history_newest_first(auth_client):
    await _post(auth_client, "2026-08-01", 90.5)
    await _post(auth_client, "2026-08-02", 89.7)
    await _post(auth_client, "2026-07-30", 91.0)
    data = (await auth_client.get("/api/weight")).json()
    dates = [entry["date"] for entry in data["entries"]]
    assert dates == ["2026-08-02", "2026-08-01", "2026-07-30"]


@pytest.mark.asyncio
async def test_startup_reconciles_active_rewards(tmp_path):
    db_path = str(tmp_path / "startup.db")
    vapid_path = str(tmp_path / "vapid_keys.json")

    # Seed a database with a user, entries + target, and a stale (revoked)
    # reward row owned by that user.
    db = Database(db_path)
    db.init_schema()
    user = db.create_user("tester", "hash", "salt")
    db.update_settings(user.id, {"target_weight": 80.0})
    db.upsert_entry(user.id, "2026-08-01", 100.0)
    db.upsert_entry(user.id, "2026-08-02", 95.0)
    with db._tx() as conn:
        conn.execute(
            "INSERT INTO active_rewards"
            " (user_id, checkpoint_percent, threshold_kg, earned_at)"
            " VALUES (?, 100, 80.0, '2020-01-01 00:00:00')",
            (user.id,),
        )
    db.close()

    # Startup must reconcile away the stale row and keep the earned ones.
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    rows = app.state.db.list_active_rewards(user.id)
    assert {r["checkpoint_percent"] for r in rows} == {10, 25}
    assert all(r["earned_at"] != "2020-01-01 00:00:00" for r in rows)
