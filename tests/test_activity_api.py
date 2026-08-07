"""API tests for exercise/meal CRUD — work unit 2.

Covers the activity-logging spec acceptance criteria: CRUD round-trips, 201
inserts, 422 validation (bad date, zero/negative duration, zero/negative
calories, unknown exercise_type, extra fields), 401 unauthenticated, 404
cross-user delete, per-user isolation, and the weight-tracking delta rule
that rewards stay weight-only (exercise/meal rows never earn checkpoints).
"""

from datetime import date, datetime
from typing import Optional

import httpx
import pytest


async def _post_exercise(
    auth_client: httpx.AsyncClient,
    date: str,
    exercise_type: str,
    duration_min: int,
    time: Optional[str] = None,
) -> httpx.Response:
    payload = {
        "date": date,
        "exercise_type": exercise_type,
        "duration_min": duration_min,
    }
    if time is not None:
        payload["time"] = time
    return await auth_client.post("/api/exercise", json=payload)


async def _post_meal(
    auth_client: httpx.AsyncClient,
    date: str,
    calories: float,
    time: Optional[str] = None,
) -> httpx.Response:
    payload = {"date": date, "calories": calories}
    if time is not None:
        payload["time"] = time
    return await auth_client.post("/api/meals", json=payload)


def _assert_local_created_at(value: str) -> None:
    """created_at must be an explicit host-local wall clock, not the SQLite
    UTC default: parseable in the local "%Y-%m-%d %H:%M:%S" format and within
    a sane window of now (a UTC default would be hours away off-UTC hosts)."""
    created = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    assert abs((datetime.now() - created).total_seconds()) < 120


# ---- exercise CRUD ---------------------------------------------------------


@pytest.mark.asyncio
async def test_exercise_insert_returns_201_and_roundtrip(auth_client):
    res = await _post_exercise(auth_client, "2026-08-01", "walk", 30)
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-08-01"
    assert body["exercise_type"] == "walk"
    assert body["duration_min"] == 30
    _assert_local_created_at(body["created_at"])

    data = (await auth_client.get("/api/exercise")).json()
    assert [e["id"] for e in data["entries"]] == [body["id"]]
    assert data["entries"][0]["exercise_type"] == "walk"


@pytest.mark.asyncio
async def test_exercise_two_entries_same_day_newest_first(auth_client):
    first = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()
    second = (await _post_exercise(auth_client, "2026-08-01", "run", 45)).json()

    # No per-date uniqueness: both persist, newest-first by id.
    data = (await auth_client.get("/api/exercise")).json()
    assert [e["id"] for e in data["entries"]] == [second["id"], first["id"]]
    assert {e["exercise_type"] for e in data["entries"]} == {"walk", "run"}


@pytest.mark.asyncio
async def test_exercise_delete_roundtrip(auth_client):
    created = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()
    res = await auth_client.delete(f"/api/exercise/{created['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}

    data = (await auth_client.get("/api/exercise")).json()
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_exercise_delete_missing_404(auth_client):
    res = await auth_client.delete("/api/exercise/9999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_exercise_bad_date_422(auth_client):
    res = await _post_exercise(auth_client, "not-a-date", "walk", 30)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exercise_zero_duration_422(auth_client):
    res = await _post_exercise(auth_client, "2026-08-01", "walk", 0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exercise_negative_duration_422(auth_client):
    res = await _post_exercise(auth_client, "2026-08-01", "walk", -10)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exercise_unknown_type_422(auth_client):
    res = await _post_exercise(auth_client, "2026-08-01", "yoga", 30)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exercise_extra_field_422(auth_client):
    res = await auth_client.post(
        "/api/exercise",
        json={
            "date": "2026-08-01",
            "exercise_type": "walk",
            "duration_min": 30,
            "notes": "felt great",
        },
    )
    assert res.status_code == 422


# ---- meal CRUD -------------------------------------------------------------


@pytest.mark.asyncio
async def test_meal_insert_returns_201_and_roundtrip(auth_client):
    res = await _post_meal(auth_client, "2026-08-01", 650.5)
    assert res.status_code == 201
    body = res.json()
    assert body["date"] == "2026-08-01"
    assert body["calories"] == 650.5
    _assert_local_created_at(body["created_at"])

    data = (await auth_client.get("/api/meals")).json()
    assert [e["id"] for e in data["entries"]] == [body["id"]]
    assert data["entries"][0]["calories"] == 650.5


@pytest.mark.asyncio
async def test_meal_two_entries_same_day(auth_client):
    first = (await _post_meal(auth_client, "2026-08-01", 400.0)).json()
    second = (await _post_meal(auth_client, "2026-08-01", 700.0)).json()

    data = (await auth_client.get("/api/meals")).json()
    assert [e["id"] for e in data["entries"]] == [second["id"], first["id"]]
    assert {e["calories"] for e in data["entries"]} == {400.0, 700.0}


@pytest.mark.asyncio
async def test_meal_delete_roundtrip(auth_client):
    created = (await _post_meal(auth_client, "2026-08-01", 500.0)).json()
    res = await auth_client.delete(f"/api/meals/{created['id']}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True}

    data = (await auth_client.get("/api/meals")).json()
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_meal_delete_missing_404(auth_client):
    res = await auth_client.delete("/api/meals/9999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_meal_bad_date_422(auth_client):
    res = await _post_meal(auth_client, "01/08/2026", 500.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_meal_zero_calories_422(auth_client):
    res = await _post_meal(auth_client, "2026-08-01", 0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_meal_negative_calories_422(auth_client):
    res = await _post_meal(auth_client, "2026-08-01", -200.0)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_meal_extra_field_422(auth_client):
    res = await auth_client.post(
        "/api/meals",
        json={"date": "2026-08-01", "calories": 500.0, "meal_type": "lunch"},
    )
    assert res.status_code == 422


# ---- authorization and isolation -------------------------------------------


@pytest.mark.asyncio
async def test_401_on_exercise_endpoints(client, auth_client, app):
    assert (await client.get("/api/exercise")).status_code == 401

    resp = await _post_exercise(client, "2026-08-01", "walk", 30)
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM exercise_entries"
    ).fetchone()[0]
    assert count == 0  # the request disclosed and persisted nothing

    created = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()
    resp = await client.delete(f"/api/exercise/{created['id']}")
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM exercise_entries"
    ).fetchone()[0]
    assert count == 1  # unauthenticated delete touched nothing


@pytest.mark.asyncio
async def test_401_on_meal_endpoints(client, auth_client, app):
    assert (await client.get("/api/meals")).status_code == 401

    resp = await _post_meal(client, "2026-08-01", 500.0)
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM meal_entries"
    ).fetchone()[0]
    assert count == 0

    created = (await _post_meal(auth_client, "2026-08-01", 500.0)).json()
    resp = await client.delete(f"/api/meals/{created['id']}")
    assert resp.status_code == 401
    count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM meal_entries"
    ).fetchone()[0]
    assert count == 1


@pytest.mark.asyncio
async def test_cross_user_exercise_delete_404_and_preserves(pair):
    alice, bob = pair
    created = (await _post_exercise(alice, "2026-08-01", "walk", 30)).json()

    resp = await bob.delete(f"/api/exercise/{created['id']}")
    assert resp.status_code == 404  # no information leak about the id

    alice_data = (await alice.get("/api/exercise")).json()
    assert [e["id"] for e in alice_data["entries"]] == [created["id"]]


@pytest.mark.asyncio
async def test_cross_user_meal_delete_404_and_preserves(pair):
    alice, bob = pair
    created = (await _post_meal(alice, "2026-08-01", 500.0)).json()

    resp = await bob.delete(f"/api/meals/{created['id']}")
    assert resp.status_code == 404

    alice_data = (await alice.get("/api/meals")).json()
    assert [e["id"] for e in alice_data["entries"]] == [created["id"]]


@pytest.mark.asyncio
async def test_activity_entries_isolated_between_users(pair):
    alice, bob = pair
    await _post_exercise(alice, "2026-08-01", "walk", 30)
    await _post_meal(alice, "2026-08-01", 500.0)

    bob_exercise = (await bob.get("/api/exercise")).json()
    assert bob_exercise["entries"] == []
    bob_meals = (await bob.get("/api/meals")).json()
    assert bob_meals["entries"] == []

    alice_exercise = (await alice.get("/api/exercise")).json()
    assert len(alice_exercise["entries"]) == 1
    alice_meals = (await alice.get("/api/meals")).json()
    assert len(alice_meals["entries"]) == 1


# ---- rewards stay weight-only (weight-tracking delta spec) -----------------


@pytest.mark.asyncio
async def test_rewards_stay_weight_only(auth_client, app):
    # Exercise/meal data alone must never earn checkpoints.
    await _post_exercise(auth_client, "2026-08-01", "walk", 30)
    await _post_meal(auth_client, "2026-08-01", 500.0)
    rewards = (await auth_client.get("/api/rewards")).json()
    assert rewards["active_checkpoints"] == []
    assert rewards["earned_count"] == 0

    # Weight entries earn checkpoints as usual…
    await auth_client.put("/api/settings", json={"target_weight": 80.0})
    await auth_client.post("/api/weight", json={"date": "2026-08-02", "weight_kg": 100.0})
    await auth_client.post("/api/weight", json={"date": "2026-08-03", "weight_kg": 95.0})
    earned = (await auth_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in earned["active_checkpoints"]] == [10, 25]

    # …and more activity must neither earn nor revoke any checkpoint.
    await _post_exercise(auth_client, "2026-08-03", "run", 45)
    await _post_meal(auth_client, "2026-08-03", 700.0)
    after = (await auth_client.get("/api/rewards")).json()
    assert [cp["percent"] for cp in after["active_checkpoints"]] == [10, 25]
    assert after["earned_count"] == 2

    # The persisted checkpoint rows are untouched by activity inserts.
    alice_id = app.state.db.get_user_by_username("tester").id
    rows = app.state.db.list_active_rewards(alice_id)
    assert {r["checkpoint_percent"] for r in rows} == {10, 25}


# ---- streaks endpoint (work unit 3) ------------------------------------------


def _today() -> str:
    """Host-local "today" — the reference date the endpoint derives streaks from."""
    return date.today().isoformat()


@pytest.mark.asyncio
async def test_streaks_returns_three_derived_counts(auth_client):
    today = _today()
    # 3 exercise rows in the current ISO week meet the min_count of 3.
    for _ in range(3):
        await _post_exercise(auth_client, today, "walk", 30)
    await _post_meal(auth_client, today, 500.0)
    await auth_client.post("/api/weight", json={"date": today, "weight_kg": 90.0})

    res = await auth_client.get("/api/streaks")
    assert res.status_code == 200
    assert res.json() == {"weight_weeks": 1, "exercise_weeks": 1, "meal_days": 1}


@pytest.mark.asyncio
async def test_streaks_reflect_deletion_without_persisted_counter(auth_client):
    today = _today()
    ids = [
        (await _post_exercise(auth_client, today, "walk", 30)).json()["id"]
        for _ in range(3)
    ]
    assert (await auth_client.get("/api/streaks")).json()["exercise_weeks"] == 1

    await auth_client.delete(f"/api/exercise/{ids[0]}")
    # 2 rows in the current week stay pending: the derived count drops to 0
    # with no persisted streak counter to update.
    assert (await auth_client.get("/api/streaks")).json()["exercise_weeks"] == 0


@pytest.mark.asyncio
async def test_streaks_isolated_between_users(pair):
    alice, bob = pair
    today = _today()
    await _post_exercise(alice, today, "walk", 30)
    await _post_exercise(alice, today, "run", 30)
    await _post_exercise(alice, today, "gym", 30)
    await _post_meal(alice, today, 500.0)
    await alice.post("/api/weight", json={"date": today, "weight_kg": 90.0})

    assert (await alice.get("/api/streaks")).json() == {
        "weight_weeks": 1,
        "exercise_weeks": 1,
        "meal_days": 1,
    }
    # Bob logged nothing: every streak derives as 0 from HIS histories only.
    assert (await bob.get("/api/streaks")).json() == {
        "weight_weeks": 0,
        "exercise_weeks": 0,
        "meal_days": 0,
    }


@pytest.mark.asyncio
async def test_streaks_401_unauthenticated(client):
    assert (await client.get("/api/streaks")).status_code == 401


# ---- optional time-of-day (activity-time) -----------------------------------


@pytest.mark.asyncio
async def test_exercise_time_roundtrip(auth_client):
    res = await _post_exercise(auth_client, "2026-08-01", "walk", 30, time="14:30")
    assert res.status_code == 201
    assert res.json()["time"] == "14:30"

    data = (await auth_client.get("/api/exercise")).json()
    assert data["entries"][0]["time"] == "14:30"


@pytest.mark.asyncio
async def test_exercise_time_absent_and_empty_are_null(auth_client):
    absent = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()
    assert absent["time"] is None
    empty = (
        await _post_exercise(auth_client, "2026-08-02", "run", 30, time="")
    ).json()
    assert empty["time"] is None

    data = (await auth_client.get("/api/exercise")).json()
    assert {e["time"] for e in data["entries"]} == {None}


@pytest.mark.parametrize("bad", ["25:99", "9am", "14:30:00"])
@pytest.mark.asyncio
async def test_exercise_invalid_time_422(auth_client, bad):
    res = await _post_exercise(auth_client, "2026-08-01", "walk", 30, time=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_meal_time_roundtrip(auth_client):
    res = await _post_meal(auth_client, "2026-08-01", 500.0, time="14:30")
    assert res.status_code == 201
    assert res.json()["time"] == "14:30"

    data = (await auth_client.get("/api/meals")).json()
    assert data["entries"][0]["time"] == "14:30"


@pytest.mark.asyncio
async def test_meal_time_absent_and_empty_are_null(auth_client):
    absent = (await _post_meal(auth_client, "2026-08-01", 500.0)).json()
    assert absent["time"] is None
    empty = (await _post_meal(auth_client, "2026-08-02", 600.0, time="")).json()
    assert empty["time"] is None

    data = (await auth_client.get("/api/meals")).json()
    assert {e["time"] for e in data["entries"]} == {None}


@pytest.mark.parametrize("bad", ["25:99", "9am", "14:30:00"])
@pytest.mark.asyncio
async def test_meal_invalid_time_422(auth_client, bad):
    res = await _post_meal(auth_client, "2026-08-01", 500.0, time=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_activity_time_extra_field_still_forbidden(auth_client):
    res = await auth_client.post(
        "/api/exercise",
        json={
            "date": "2026-08-01",
            "exercise_type": "walk",
            "duration_min": 30,
            "time": "14:30",
            "notes": "felt great",
        },
    )
    assert res.status_code == 422

    res = await auth_client.post(
        "/api/meals",
        json={
            "date": "2026-08-01",
            "calories": 500.0,
            "time": "14:30",
            "meal_type": "lunch",
        },
    )
    assert res.status_code == 422

# ---- edit (PUT) ------------------------------------------------------------


async def _put_exercise(
    auth_client: httpx.AsyncClient,
    entry_id: int,
    date: str,
    exercise_type: str,
    duration_min: int,
    time: Optional[str] = None,
) -> httpx.Response:
    payload = {
        "date": date,
        "exercise_type": exercise_type,
        "duration_min": duration_min,
    }
    if time is not None:
        payload["time"] = time
    return await auth_client.put(f"/api/exercise/{entry_id}", json=payload)


async def _put_meal(
    auth_client: httpx.AsyncClient,
    entry_id: int,
    date: str,
    calories: float,
    time: Optional[str] = None,
) -> httpx.Response:
    payload = {"date": date, "calories": calories}
    if time is not None:
        payload["time"] = time
    return await auth_client.put(f"/api/meals/{entry_id}", json=payload)


@pytest.mark.asyncio
async def test_exercise_put_roundtrip(auth_client):
    created = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()

    res = await _put_exercise(
        auth_client, created["id"], "2026-08-03", "run", 45, time="14:30"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == created["id"]
    assert body["date"] == "2026-08-03"
    assert body["time"] == "14:30"
    assert body["exercise_type"] == "run"
    assert body["duration_min"] == 45
    assert body["created_at"] == created["created_at"]  # edits never touch it

    data = (await auth_client.get("/api/exercise")).json()
    assert [e["id"] for e in data["entries"]] == [created["id"]]
    assert data["entries"][0]["exercise_type"] == "run"
    assert data["entries"][0]["duration_min"] == 45


@pytest.mark.asyncio
async def test_meal_put_roundtrip(auth_client):
    created = (await _post_meal(auth_client, "2026-08-01", 500.0)).json()

    res = await _put_meal(
        auth_client, created["id"], "2026-08-02", 725.5, time="19:15"
    )
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == created["id"]
    assert body["date"] == "2026-08-02"
    assert body["time"] == "19:15"
    assert body["calories"] == 725.5
    assert body["created_at"] == created["created_at"]

    data = (await auth_client.get("/api/meals")).json()
    assert data["entries"][0]["calories"] == 725.5


@pytest.mark.asyncio
async def test_exercise_put_missing_404(auth_client):
    res = await _put_exercise(auth_client, 9999, "2026-08-01", "walk", 30)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_meal_put_missing_404(auth_client):
    res = await _put_meal(auth_client, 9999, "2026-08-01", 500.0)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_exercise_put_404_and_preserves(pair):
    alice, bob = pair
    created = (await _post_exercise(alice, "2026-08-01", "walk", 30)).json()

    res = await _put_exercise(bob, created["id"], "2026-08-02", "run", 45)
    assert res.status_code == 404  # no information leak about the id

    alice_data = (await alice.get("/api/exercise")).json()
    assert alice_data["entries"][0]["exercise_type"] == "walk"
    assert alice_data["entries"][0]["duration_min"] == 30


@pytest.mark.asyncio
async def test_cross_user_meal_put_404_and_preserves(pair):
    alice, bob = pair
    created = (await _post_meal(alice, "2026-08-01", 500.0)).json()

    res = await _put_meal(bob, created["id"], "2026-08-02", 900.0)
    assert res.status_code == 404

    alice_data = (await alice.get("/api/meals")).json()
    assert alice_data["entries"][0]["calories"] == 500.0


@pytest.mark.parametrize("bad", ["25:99", "9am", "14:30:00"])
@pytest.mark.asyncio
async def test_exercise_put_invalid_time_422(auth_client, bad):
    created = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()
    res = await _put_exercise(
        auth_client, created["id"], "2026-08-01", "walk", 30, time=bad
    )
    assert res.status_code == 422


@pytest.mark.parametrize("duration", [0, -10])
@pytest.mark.asyncio
async def test_exercise_put_bad_duration_422(auth_client, duration):
    created = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()
    res = await _put_exercise(
        auth_client, created["id"], "2026-08-01", "walk", duration
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exercise_put_extra_field_422(auth_client):
    created = (await _post_exercise(auth_client, "2026-08-01", "walk", 30)).json()
    res = await auth_client.put(
        f"/api/exercise/{created['id']}",
        json={
            "date": "2026-08-01",
            "exercise_type": "run",
            "duration_min": 45,
            "notes": "felt great",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_meal_put_extra_field_422(auth_client):
    created = (await _post_meal(auth_client, "2026-08-01", 500.0)).json()
    res = await auth_client.put(
        f"/api/meals/{created['id']}",
        json={"date": "2026-08-01", "calories": 700.0, "meal_type": "lunch"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_exercise_put_empty_time_becomes_null(auth_client):
    created = (
        await _post_exercise(auth_client, "2026-08-01", "walk", 30, time="14:30")
    ).json()
    res = await _put_exercise(
        auth_client, created["id"], "2026-08-01", "walk", 30, time=""
    )
    assert res.status_code == 200
    assert res.json()["time"] is None

    data = (await auth_client.get("/api/exercise")).json()
    assert data["entries"][0]["time"] is None


@pytest.mark.asyncio
async def test_meal_put_empty_time_becomes_null(auth_client):
    created = (
        await _post_meal(auth_client, "2026-08-01", 500.0, time="14:30")
    ).json()
    res = await _put_meal(auth_client, created["id"], "2026-08-01", 500.0, time="")
    assert res.status_code == 200
    assert res.json()["time"] is None

    data = (await auth_client.get("/api/meals")).json()
    assert data["entries"][0]["time"] is None
