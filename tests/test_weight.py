"""API tests for weight logging: add, update-on-duplicate, delete, validation."""

import pytest

from database import Database
from main import create_app, init_app_state


_UNSET = object()


def _post(auth_client, date, weight_kg, time=_UNSET):
    payload = {"date": date, "weight_kg": weight_kg}
    if time is not _UNSET:
        payload["time"] = time
    return auth_client.post(
        "/api/weight",
        json=payload,
    )


def _put(auth_client, entry_id, date, weight_kg, time=_UNSET):
    payload = {"date": date, "weight_kg": weight_kg}
    if time is not _UNSET:
        payload["time"] = time
    return auth_client.put(
        f"/api/weight/{entry_id}",
        json=payload,
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
async def test_put_updates_weight(auth_client):
    created = (await _post(auth_client, "2026-08-01", 90.5)).json()
    res = await _put(auth_client, created["id"], "2026-08-01", 88.0)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == created["id"]
    assert body["date"] == "2026-08-01"
    assert body["weight_kg"] == 88.0
    # created_at is preserved: PUT edits, it does not re-log.
    assert body["created_at"] == created["created_at"]

    data = (await auth_client.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["weight_kg"] == 88.0
    assert data["summary"]["current_kg"] == 88.0


@pytest.mark.asyncio
async def test_put_moves_date(auth_client):
    created = (await _post(auth_client, "2026-08-01", 90.5)).json()
    res = await _put(auth_client, created["id"], "2026-08-05", 90.5)
    assert res.status_code == 200
    assert res.json()["date"] == "2026-08-05"

    data = (await auth_client.get("/api/weight")).json()
    assert [e["date"] for e in data["entries"]] == ["2026-08-05"]
    assert "2026-08-01" not in [e["date"] for e in data["entries"]]


@pytest.mark.asyncio
async def test_put_date_conflict_409(auth_client):
    a = (await _post(auth_client, "2026-08-01", 90.5)).json()
    b = (await _post(auth_client, "2026-08-02", 88.0)).json()
    res = await _put(auth_client, a["id"], "2026-08-02", 85.0)
    assert res.status_code == 409
    assert res.json()["detail"] == "date already has an entry"

    # No partial update: both original entries are untouched.
    data = (await auth_client.get("/api/weight")).json()
    by_date = {e["date"]: e["weight_kg"] for e in data["entries"]}
    assert by_date == {"2026-08-02": 88.0, "2026-08-01": 90.5}
    assert all(e["id"] in (a["id"], b["id"]) for e in data["entries"])


@pytest.mark.asyncio
async def test_put_missing_entry_404(auth_client):
    res = await _put(auth_client, 9999, "2026-08-01", 85.0)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_put_cross_user_404(pair):
    alice, bob = pair
    created = (await _post(alice, "2026-08-01", 90.5)).json()
    # bob owns a date that alice's entry would conflict on; ownership is
    # checked before the date conflict, so this still 404s (no info leak).
    await _post(bob, "2026-08-02", 88.0)
    res = await bob.put(
        f"/api/weight/{created['id']}",
        json={"date": "2026-08-02", "weight_kg": 85.0},
    )
    assert res.status_code == 404

    data = (await alice.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["weight_kg"] == 90.5


@pytest.mark.asyncio
async def test_put_bad_date_422(auth_client):
    created = (await _post(auth_client, "2026-08-01", 90.5)).json()
    res = await _put(auth_client, created["id"], "not-a-date", 85.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_put_extra_field_422(auth_client):
    created = (await _post(auth_client, "2026-08-01", 90.5)).json()
    res = await auth_client.put(
        f"/api/weight/{created['id']}",
        json={"date": "2026-08-02", "weight_kg": 85.0, "calories": 400},
    )
    assert res.status_code == 422

    data = (await auth_client.get("/api/weight")).json()
    assert [e["date"] for e in data["entries"]] == ["2026-08-01"]


@pytest.mark.asyncio
async def test_post_upsert_unchanged(auth_client):
    # Guard: PUT must not change POST semantics — posting to an existing date
    # still updates in place and returns 200.
    await _post(auth_client, "2026-08-01", 90.5)
    res = await _post(auth_client, "2026-08-01", 87.5)
    assert res.status_code == 200
    assert res.json()["weight_kg"] == 87.5

    data = (await auth_client.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["weight_kg"] == 87.5


@pytest.mark.asyncio
async def test_post_with_time_roundtrip(auth_client):
    res = await _post(auth_client, "2026-08-01", 90.5, time="08:30")
    assert res.status_code == 201
    assert res.json()["time"] == "08:30"

    data = (await auth_client.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["time"] == "08:30"


@pytest.mark.asyncio
async def test_time_absent_and_empty_normalize_to_null(auth_client):
    # Truly absent: no time key in the payload.
    res = await _post(auth_client, "2026-08-01", 90.5)
    assert res.status_code == 201
    assert res.json()["time"] is None

    # Empty string: the validator normalizes it to None.
    res = await _post(auth_client, "2026-08-02", 89.5, time="")
    assert res.status_code == 201
    assert res.json()["time"] is None

    data = (await auth_client.get("/api/weight")).json()
    times = {e["date"]: e["time"] for e in data["entries"]}
    assert times == {"2026-08-01": None, "2026-08-02": None}


@pytest.mark.asyncio
async def test_invalid_time_rejected_on_post(auth_client):
    for bad in ("25:99", "9am"):
        res = await _post(auth_client, "2026-08-01", 90.5, time=bad)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_invalid_time_rejected_on_put(auth_client):
    created = (await _post(auth_client, "2026-08-01", 90.5)).json()
    for bad in ("25:99", "9am"):
        res = await _put(auth_client, created["id"], "2026-08-01", 88.0, time=bad)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_post_upsert_updates_time(auth_client):
    res = await _post(auth_client, "2026-08-01", 90.5, time="08:30")
    assert res.json()["time"] == "08:30"

    res = await _post(auth_client, "2026-08-01", 88.0, time="21:45")
    assert res.status_code == 200
    assert res.json()["time"] == "21:45"

    data = (await auth_client.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["time"] == "21:45"


@pytest.mark.asyncio
async def test_put_preserves_and_updates_time(auth_client):
    created = (await _post(auth_client, "2026-08-01", 90.5, time="08:30")).json()

    # Editing with the same time keeps it.
    res = await _put(auth_client, created["id"], "2026-08-01", 88.0, time="08:30")
    assert res.status_code == 200
    assert res.json()["time"] == "08:30"

    # Editing with a new time replaces it.
    res = await _put(auth_client, created["id"], "2026-08-01", 88.0, time="21:45")
    assert res.status_code == 200
    assert res.json()["time"] == "21:45"

    data = (await auth_client.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["time"] == "21:45"


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
