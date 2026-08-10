"""API tests for mood CRUD — work unit 5, S3a (r1-quests-xp).

Covers the mood-logging spec acceptance criteria: 201 inserts with the
mood/note contract (integer 1-5, optional note of at most 500 characters),
multiple entries per user per day, GET newest-first ordering, 422 validation
(mood out of range, over-long note, bad date/time, extra fields), 401
unauthenticated, 404 delete of missing/foreign entries, and per-user
isolation.
"""

from datetime import date, datetime
from typing import Optional

import httpx
import pytest


async def _post_mood(
    auth_client: httpx.AsyncClient,
    mood: int,
    date: Optional[str] = None,
    note: Optional[str] = None,
    time: Optional[str] = None,
) -> httpx.Response:
    payload: dict[str, object] = {"mood": mood}
    if date is not None:
        payload["date"] = date
    if note is not None:
        payload["note"] = note
    if time is not None:
        payload["time"] = time
    return await auth_client.post("/api/mood", json=payload)


def _assert_local_created_at(value: str) -> None:
    """created_at must be an explicit host-local wall clock, not the SQLite
    UTC default: parseable in the local "%Y-%m-%d %H:%M:%S" format and within
    a sane window of now (a UTC default would be hours away off-UTC hosts)."""
    created = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    assert abs((datetime.now() - created).total_seconds()) < 120


# ---- entry-style contract (spec 'Mood Entry Contract') ---------------------


def test_mood_entry_dataclass_is_entry_style():
    """The amended spec pins the entry-style convention: the owner id is a
    column of the persisted table and an ownership filter of every API query,
    never a field of the MoodEntry record itself (mirroring
    WeightEntry/ExerciseEntry/MealEntry). The dataclass fields must not carry
    user_id while the table schema must."""
    from models import MoodEntry

    assert "user_id" not in MoodEntry.__dataclass_fields__, (
        "MoodEntry must stay entry-style: owner id lives in the persistence layer"
    )


def test_mood_entries_table_carries_owner_column():
    """The persisted table, not the dataclass, carries the owner id (spec
    'Mood Entry Contract')."""
    from database import SCHEMA_STATEMENTS

    assert any(
        "mood_entries" in stmt and "user_id INTEGER NOT NULL" in stmt
        for stmt in SCHEMA_STATEMENTS
    )


# ---- mood CRUD ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_mood_insert_returns_201_and_roundtrip(auth_client):
    res = await _post_mood(auth_client, 4, date="2026-08-01", note="feeling good")
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-08-01"
    assert body["mood"] == 4
    assert body["note"] == "feeling good"
    assert body["time"] is None
    _assert_local_created_at(body["created_at"])

    data = (await auth_client.get("/api/mood")).json()
    assert [e["id"] for e in data["entries"]] == [body["id"]]
    assert data["entries"][0]["mood"] == 4


@pytest.mark.asyncio
async def test_mood_date_defaults_to_today(auth_client):
    res = await _post_mood(auth_client, 3)
    assert res.status_code == 201
    assert res.json()["date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_mood_two_entries_same_day_newest_first(auth_client):
    first = (await _post_mood(auth_client, 2, date="2026-08-01")).json()
    second = (await _post_mood(auth_client, 4, date="2026-08-01")).json()

    # No per-date uniqueness: both persist, newest-first by id.
    data = (await auth_client.get("/api/mood")).json()
    assert [e["id"] for e in data["entries"]] == [second["id"], first["id"]]
    assert {e["mood"] for e in data["entries"]} == {2, 4}


@pytest.mark.asyncio
async def test_mood_delete_roundtrip(auth_client):
    created = (await _post_mood(auth_client, 5, date="2026-08-01")).json()
    res = await auth_client.delete(f"/api/mood/{created['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}

    data = (await auth_client.get("/api/mood")).json()
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_mood_delete_missing_404(auth_client):
    res = await auth_client.delete("/api/mood/9999")
    assert res.status_code == 404


# ---- validation --------------------------------------------------------------


@pytest.mark.parametrize("bad_mood", [0, 6, -1])
@pytest.mark.asyncio
async def test_mood_out_of_range_422(auth_client, bad_mood):
    res = await _post_mood(auth_client, bad_mood, date="2026-08-01")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_mood_note_too_long_422(auth_client):
    res = await _post_mood(auth_client, 3, date="2026-08-01", note="x" * 501)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_mood_note_500_chars_accepted(auth_client):
    res = await _post_mood(auth_client, 3, date="2026-08-01", note="x" * 500)
    assert res.status_code == 201
    assert len(res.json()["note"]) == 500


@pytest.mark.asyncio
async def test_mood_bad_date_422(auth_client):
    res = await _post_mood(auth_client, 3, date="not-a-date")
    assert res.status_code == 422


@pytest.mark.parametrize("bad", ["25:99", "9am", "14:30:00"])
@pytest.mark.asyncio
async def test_mood_invalid_time_422(auth_client, bad):
    res = await _post_mood(auth_client, 3, date="2026-08-01", time=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_mood_extra_field_422(auth_client):
    res = await auth_client.post(
        "/api/mood",
        json={"date": "2026-08-01", "mood": 3, "feeling": "great"},
    )
    assert res.status_code == 422


# ---- authorization and isolation ---------------------------------------------


@pytest.mark.asyncio
async def test_401_on_mood_endpoints(client, auth_client, app):
    assert (await client.get("/api/mood")).status_code == 401

    resp = await _post_mood(client, 3, date="2026-08-01")
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM mood_entries"
    ).fetchone()[0]
    assert count == 0  # the request disclosed and persisted nothing

    created = (await _post_mood(auth_client, 3, date="2026-08-01")).json()
    resp = await client.delete(f"/api/mood/{created['id']}")
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM mood_entries"
    ).fetchone()[0]
    assert count == 1  # unauthenticated delete touched nothing


@pytest.mark.asyncio
async def test_cross_user_mood_delete_404_and_preserves(pair):
    alice, bob = pair
    created = (await _post_mood(alice, 3, date="2026-08-01")).json()

    resp = await bob.delete(f"/api/mood/{created['id']}")
    assert resp.status_code == 404  # no information leak about the id

    alice_data = (await alice.get("/api/mood")).json()
    assert [e["id"] for e in alice_data["entries"]] == [created["id"]]


@pytest.mark.asyncio
async def test_mood_entries_isolated_between_users(pair):
    alice, bob = pair
    await _post_mood(alice, 5, date="2026-08-01")

    bob_data = (await bob.get("/api/mood")).json()
    assert bob_data["entries"] == []

    alice_data = (await alice.get("/api/mood")).json()
    assert len(alice_data["entries"]) == 1
