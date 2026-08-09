"""API tests for habit CRUD — work unit 5, S3a (r1-quests-xp).

Covers the habit-logging spec acceptance criteria: 201 inserts against the
fixed v1 catalogue (water, fruit_veg, home_cooked, sleep_routine), multiple
entries per user per day, GET newest-first ordering, 422 validation (unknown
habit_type, bad date/time, extra fields), 401 unauthenticated, 404 delete of
missing/foreign entries, and per-user isolation.
"""

from datetime import date, datetime
from typing import Optional

import httpx
import pytest


async def _post_habit(
    auth_client: httpx.AsyncClient,
    habit_type: str,
    date: Optional[str] = None,
    time: Optional[str] = None,
) -> httpx.Response:
    payload: dict[str, object] = {"habit_type": habit_type}
    if date is not None:
        payload["date"] = date
    if time is not None:
        payload["time"] = time
    return await auth_client.post("/api/habits", json=payload)


def _assert_local_created_at(value: str) -> None:
    """created_at must be an explicit host-local wall clock, not the SQLite
    UTC default: parseable in the local "%Y-%m-%d %H:%M:%S" format and within
    a sane window of now (a UTC default would be hours away off-UTC hosts)."""
    created = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    assert abs((datetime.now() - created).total_seconds()) < 120


# ---- habit CRUD ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_habit_insert_returns_201_and_roundtrip(auth_client):
    res = await _post_habit(auth_client, "water", date="2026-08-01", time="14:30")
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-08-01"
    assert body["habit_type"] == "water"
    assert body["time"] == "14:30"
    _assert_local_created_at(body["created_at"])

    data = (await auth_client.get("/api/habits")).json()
    assert [e["id"] for e in data["entries"]] == [body["id"]]
    assert data["entries"][0]["habit_type"] == "water"


@pytest.mark.asyncio
async def test_habit_date_defaults_to_today(auth_client):
    res = await _post_habit(auth_client, "water")
    assert res.status_code == 201
    assert res.json()["date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_habit_two_entries_same_day_newest_first(auth_client):
    first = (await _post_habit(auth_client, "water", date="2026-08-01")).json()
    second = (await _post_habit(auth_client, "home_cooked", date="2026-08-01")).json()

    # No per-date uniqueness: both persist, newest-first by id.
    data = (await auth_client.get("/api/habits")).json()
    assert [e["id"] for e in data["entries"]] == [second["id"], first["id"]]
    assert {e["habit_type"] for e in data["entries"]} == {"water", "home_cooked"}


@pytest.mark.asyncio
async def test_habit_delete_roundtrip(auth_client):
    created = (await _post_habit(auth_client, "water", date="2026-08-01")).json()
    res = await auth_client.delete(f"/api/habits/{created['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}

    data = (await auth_client.get("/api/habits")).json()
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_habit_delete_missing_404(auth_client):
    res = await auth_client.delete("/api/habits/9999")
    assert res.status_code == 404


# ---- validation ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_habit_unknown_type_422(auth_client):
    res = await _post_habit(auth_client, "meditation", date="2026-08-01")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_habit_all_four_catalogue_types_accepted(auth_client):
    # Imported here so this file collects even before constants.HABIT_TYPES
    # exists (RED phase); the value set itself is pinned by the drift guard.
    from constants import HABIT_TYPES

    for habit_type in HABIT_TYPES:
        res = await _post_habit(auth_client, habit_type, date="2026-08-01")
        assert res.status_code == 201, habit_type
        assert res.json()["habit_type"] == habit_type


@pytest.mark.asyncio
async def test_habit_bad_date_422(auth_client):
    res = await _post_habit(auth_client, "water", date="01/08/2026")
    assert res.status_code == 422


@pytest.mark.parametrize("bad", ["25:99", "9am", "14:30:00"])
@pytest.mark.asyncio
async def test_habit_invalid_time_422(auth_client, bad):
    res = await _post_habit(auth_client, "water", date="2026-08-01", time=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_habit_extra_field_422(auth_client):
    res = await auth_client.post(
        "/api/habits",
        json={"date": "2026-08-01", "habit_type": "water", "count": 8},
    )
    assert res.status_code == 422


# ---- authorization and isolation ---------------------------------------------


@pytest.mark.asyncio
async def test_401_on_habit_endpoints(client, auth_client, app):
    assert (await client.get("/api/habits")).status_code == 401

    resp = await _post_habit(client, "water", date="2026-08-01")
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM habit_entries"
    ).fetchone()[0]
    assert count == 0  # the request disclosed and persisted nothing

    created = (await _post_habit(auth_client, "water", date="2026-08-01")).json()
    resp = await client.delete(f"/api/habits/{created['id']}")
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM habit_entries"
    ).fetchone()[0]
    assert count == 1  # unauthenticated delete touched nothing


@pytest.mark.asyncio
async def test_cross_user_habit_delete_404_and_preserves(pair):
    alice, bob = pair
    created = (await _post_habit(alice, "water", date="2026-08-01")).json()

    resp = await bob.delete(f"/api/habits/{created['id']}")
    assert resp.status_code == 404  # no information leak about the id

    alice_data = (await alice.get("/api/habits")).json()
    assert [e["id"] for e in alice_data["entries"]] == [created["id"]]


@pytest.mark.asyncio
async def test_habit_entries_isolated_between_users(pair):
    alice, bob = pair
    await _post_habit(alice, "sleep_routine", date="2026-08-01")

    bob_data = (await bob.get("/api/habits")).json()
    assert bob_data["entries"] == []

    alice_data = (await alice.get("/api/habits")).json()
    assert len(alice_data["entries"]) == 1
