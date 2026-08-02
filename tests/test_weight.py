"""API tests for weight logging: add, update-on-duplicate, delete, validation."""

import pytest


def _post(client, date, weight_kg):
    return client.post(
        "/api/weight",
        json={"date": date, "weight_kg": weight_kg},
    )


@pytest.mark.asyncio
async def test_add_entry(client):
    res = await _post(client, "2026-08-01", 90.5)
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-08-01"
    assert body["weight_kg"] == 90.5

    got = await client.get("/api/weight")
    data = got.json()
    assert len(data["entries"]) == 1
    assert data["summary"]["baseline_kg"] == 90.5
    assert data["summary"]["current_kg"] == 90.5
    assert data["summary"]["lost_kg"] == 0.0


@pytest.mark.asyncio
async def test_update_on_duplicate_date(client):
    await _post(client, "2026-08-01", 90.5)
    res = await _post(client, "2026-08-01", 88.0)
    assert res.status_code == 200
    assert res.json()["weight_kg"] == 88.0

    data = (await client.get("/api/weight")).json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["weight_kg"] == 88.0


@pytest.mark.asyncio
async def test_delete_entry(client):
    created = (await _post(client, "2026-08-01", 90.5)).json()
    res = await client.delete(f"/api/weight/{created['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}

    data = (await client.get("/api/weight")).json()
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_delete_missing_entry_404(client):
    res = await client.delete("/api/weight/9999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_negative_weight_rejected(client):
    res = await _post(client, "2026-08-01", -5.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_zero_weight_rejected(client):
    res = await _post(client, "2026-08-01", 0.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_bad_date_rejected(client):
    res = await _post(client, "not-a-date", 85.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_history_newest_first(client):
    await _post(client, "2026-08-01", 90.5)
    await _post(client, "2026-08-02", 89.7)
    await _post(client, "2026-07-30", 91.0)
    data = (await client.get("/api/weight")).json()
    dates = [entry["date"] for entry in data["entries"]]
    assert dates == ["2026-08-02", "2026-08-01", "2026-07-30"]
