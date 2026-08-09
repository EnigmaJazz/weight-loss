"""API integration tests for POST /api/onboarding.

These assert the user-onboarding spec's contract through the httpx
ASGITransport harness: 401/422 rejections (with nothing persisted), the
height-before-BMI-bounds validation order (design AD6), atomic completion,
idempotent re-POST, and full rollback when the weight insert fails
mid-transaction.
"""

from datetime import date
from typing import Any, NoReturn, Optional

import httpx
import pytest
import sqlite3
from fastapi import FastAPI

import database as database_module
from tests.conftest import auth_user_id


def _payload(**overrides: Any) -> dict[str, Any]:
    """A fully valid onboarding payload; overrides replace fields.

    The four goals/lifestyle fields are optional per spec, so a fully valid
    payload carries them; the allowlist-rejection tests override them with
    out-of-allowlist values.
    """
    body = {
        "height_cm": 175.0,
        "weight_kg": 80.0,
        "target_weight": 70.0,
        "weight_unit": "kg",
        "height_unit": "cm",
        "target_unit": "kg",
        "weight_display": "lb",
        "tip_time": "09:30",
        "reminder_time": "20:30",
        "reminder_weekday": 2,
        "exercise_time": "17:30",
        "primary_goal": "fitness",
        "secondary_goals": ["strength", "stamina"],
        "health_domains": ["nutrition", "sleep"],
        "activity_level": "moderate",
    }
    body.update(overrides)
    return body


def _settings_count(app: FastAPI, user_id: int) -> int:
    return app.state.db.conn.execute(
        "SELECT COUNT(*) FROM settings WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def _weight_count(app: FastAPI, user_id: int) -> int:
    return app.state.db.conn.execute(
        "SELECT COUNT(*) FROM weight_entries WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


# ---- authorization -------------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_requires_auth(client, app):
    """Spec: no valid session -> 401 and nothing persisted."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "password": "password123",
            "email": "alice@example.com",
        },
    )
    assert resp.status_code == 201
    await client.post("/api/auth/logout")  # drop the session cookie

    resp = await client.post("/api/onboarding", json=_payload())
    assert resp.status_code == 401
    assert _settings_count(app, 1) == 0
    assert _weight_count(app, 1) == 0


# ---- validation: XOR and unknown keys ------------------------------------


@pytest.mark.asyncio
async def test_onboarding_rejects_both_targets(auth_client, app):
    """Spec: both target_weight and target_bmi -> 422, persists nothing."""
    resp = await auth_client.post(
        "/api/onboarding", json=_payload(target_bmi=22.0)
    )
    assert resp.status_code == 422
    user_id = auth_user_id(app)
    assert _settings_count(app, user_id) == 0
    assert _weight_count(app, user_id) == 0


@pytest.mark.asyncio
async def test_onboarding_rejects_neither_target(auth_client, app):
    """Spec: neither target_weight nor target_bmi -> 422, persists nothing."""
    resp = await auth_client.post(
        "/api/onboarding", json=_payload(target_weight=None)
    )
    assert resp.status_code == 422
    user_id = auth_user_id(app)
    assert _settings_count(app, user_id) == 0
    assert _weight_count(app, user_id) == 0


@pytest.mark.asyncio
async def test_onboarding_rejects_unknown_key(auth_client, app):
    """Spec: unknown key (extra="forbid") -> 422, persists nothing."""
    resp = await auth_client.post(
        "/api/onboarding", json=_payload(favorite_color="red")
    )
    assert resp.status_code == 422
    user_id = auth_user_id(app)
    assert _settings_count(app, user_id) == 0
    assert _weight_count(app, user_id) == 0


@pytest.mark.asyncio
async def test_onboarding_rejects_theme_key(auth_client, app):
    """Spec (theme-preference): theme must NOT be an accepted onboarding key;
    OnboardingIn stays untouched (extra="forbid")."""
    resp = await auth_client.post(
        "/api/onboarding", json=_payload(theme="dark")
    )
    assert resp.status_code == 422
    user_id = auth_user_id(app)
    assert _settings_count(app, user_id) == 0
    assert _weight_count(app, user_id) == 0


# ---- validation order (design AD6) ---------------------------------------


@pytest.mark.asyncio
async def test_onboarding_height_checked_before_bmi_bounds(auth_client, app):
    """Spec: missing/non-positive height -> 422 names height, never BMI bounds.

    target_bmi 50 passes the field-level gt=0 constraint and the (10, 40]
    bounds live in the model validator, which does not run when field
    validation already failed — so the errors MUST mention only height_cm.
    """
    # Missing height entirely.
    resp = await auth_client.post(
        "/api/onboarding",
        json={"weight_kg": 80.0, "target_bmi": 50.0},
    )
    assert resp.status_code == 422
    errors = resp.json()["detail"]
    locs = [e["loc"] for e in errors]
    assert ["body", "height_cm"] in locs
    assert "target_bmi" not in " ".join(str(e["msg"]) for e in errors)

    # Non-positive height.
    resp = await auth_client.post(
        "/api/onboarding",
        json={"height_cm": 0.0, "weight_kg": 80.0, "target_bmi": 50.0},
    )
    assert resp.status_code == 422
    errors = resp.json()["detail"]
    locs = [e["loc"] for e in errors]
    assert ["body", "height_cm"] in locs
    assert "target_bmi" not in " ".join(str(e["msg"]) for e in errors)

    user_id = auth_user_id(app)
    assert _settings_count(app, user_id) == 0
    assert _weight_count(app, user_id) == 0


@pytest.mark.asyncio
async def test_onboarding_target_bmi_bounds_with_valid_height(auth_client, app):
    """With height valid, (10, 40] bounds surface as a target_bmi error."""
    over = await auth_client.post(
        "/api/onboarding",
        json=_payload(target_weight=None, target_bmi=40.5),
    )
    assert over.status_code == 422
    msgs = " ".join(str(e["msg"]) for e in over.json()["detail"])
    assert "target_bmi" in msgs

    under = await auth_client.post(
        "/api/onboarding",
        json=_payload(target_weight=None, target_bmi=10.0),
    )
    assert under.status_code == 422

    # Inclusive upper boundary: 40 is accepted.
    boundary = await auth_client.post(
        "/api/onboarding",
        json=_payload(target_weight=None, target_bmi=40.0),
    )
    assert boundary.status_code == 200
    assert boundary.json() == {"ok": True}


# ---- atomic completion ---------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_happy_path_atomic(auth_client, app):
    """Spec: settings (height, target, prefs, flag) + exactly one today
    entry + rewards reconciled, all from one POST."""
    user_id = auth_user_id(app)
    # A pre-existing older entry makes reconciliation meaningful: baseline 85
    # -> target 70 -> 10% (83.5) and 25% (81.25) checkpoints are earned once
    # today's 80 kg lands.
    plant = await auth_client.post(
        "/api/weight", json={"date": "2026-07-01", "weight_kg": 85.0}
    )
    assert plant.status_code == 201, plant.text

    resp = await auth_client.post("/api/onboarding", json=_payload())
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    settings = (await auth_client.get("/api/settings")).json()
    assert settings["height_cm"] == 175.0
    assert settings["target_weight"] == 70.0
    assert settings["target_bmi"] is None
    assert settings["onboarding_complete"] is True
    assert settings["weight_unit"] == "kg"
    assert settings["height_unit"] == "cm"
    assert settings["target_unit"] == "kg"
    assert settings["weight_display"] == "lb"
    assert settings["tip_time"] == "09:30"
    assert settings["reminder_time"] == "20:30"
    assert settings["reminder_weekday"] == 2
    assert settings["exercise_time"] == "17:30"
    # Spec (user-onboarding): the four optional goals/lifestyle fields persist
    # with their exact values and list order.
    assert settings["primary_goal"] == "fitness"
    assert settings["secondary_goals"] == ["strength", "stamina"]
    assert settings["health_domains"] == ["nutrition", "sleep"]
    assert settings["activity_level"] == "moderate"

    today = date.today().isoformat()
    dates = sorted(
        row["date"]
        for row in app.state.db.conn.execute(
            "SELECT date FROM weight_entries WHERE user_id = ?", (user_id,)
        ).fetchall()
    )
    assert dates == ["2026-07-01", today]
    today_count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM weight_entries WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()[0]
    assert today_count == 1

    rewards = (await auth_client.get("/api/rewards")).json()
    assert rewards["earned_count"] == 2
    assert {cp["percent"] for cp in rewards["active_checkpoints"]} == {10, 25}
    assert rewards["target_kg"] == 70.0


@pytest.mark.asyncio
async def test_onboarding_idempotent_repost(auth_client, app):
    """Spec: re-POSTing keeps a single today entry and overwrites settings."""
    user_id = auth_user_id(app)
    first = await auth_client.post("/api/onboarding", json=_payload())
    assert first.status_code == 200

    second = await auth_client.post("/api/onboarding", json=_payload())
    assert second.status_code == 200

    today = date.today().isoformat()
    today_count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM weight_entries WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()[0]
    assert today_count == 1

    # Settings are overwritten (k/v upsert), not appended: row count is
    # stable and a changed preference on a third POST is reflected.
    rows_before = _settings_count(app, user_id)
    assert rows_before > 0
    third = await auth_client.post(
        "/api/onboarding",
        json=_payload(weight_unit="st-lb", primary_goal="wellbeing",
                      secondary_goals=["flexibility", "mobility"]),
    )
    assert third.status_code == 200
    assert _settings_count(app, user_id) == rows_before
    settings = (await auth_client.get("/api/settings")).json()
    assert settings["weight_unit"] == "st-lb"
    # Goals/lifestyle are overwritten by a re-POST, never appended.
    assert settings["primary_goal"] == "wellbeing"
    assert settings["secondary_goals"] == ["flexibility", "mobility"]
    assert settings["health_domains"] == ["nutrition", "sleep"]
    today_count = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM weight_entries WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()[0]
    assert today_count == 1


@pytest.mark.asyncio
async def test_onboarding_mid_tx_failure_rolls_back(app, monkeypatch):
    """Spec: a weight-insert failure mid-transaction persists NO settings,
    weight, or reward change.

    The transport runs with raise_app_exceptions=False so the 500 Starlette
    sends is observable: ServerErrorMiddleware always re-raises after sending
    the response (starlette 1.3.1), and the default transport would re-raise
    the injected error into the test instead.
    """
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/auth/register",
            json={
                "username": "tester",
                "password": "password123",
                "email": "tester@example.com",
            },
        )
        assert resp.status_code == 201, resp.text
        user_id = resp.json()["id"]
        plant = await client.post(
            "/api/weight", json={"date": "2026-07-01", "weight_kg": 85.0}
        )
        assert plant.status_code == 201, plant.text

        def _boom(
            self,
            conn: sqlite3.Connection,
            user_id: int,
            date: str,
            weight_kg: float,
            time: Optional[str],
        ) -> NoReturn:
            raise RuntimeError("injected mid-transaction failure")

        monkeypatch.setattr(database_module.Database, "_upsert_entry_conn", _boom)

        resp = await client.post("/api/onboarding", json=_payload())
        assert resp.status_code == 500

        # Settings batch (height/target/prefs/onboarding_complete) rolled back.
        keys = [
            row["key"]
            for row in app.state.db.conn.execute(
                "SELECT key FROM settings WHERE user_id = ?", (user_id,)
            ).fetchall()
        ]
        assert keys == []
        # Today's entry rolled back; only the planted row remains.
        dates = [
            row["date"]
            for row in app.state.db.conn.execute(
                "SELECT date FROM weight_entries WHERE user_id = ?", (user_id,)
            ).fetchall()
        ]
        assert dates == ["2026-07-01"]
        # Rewards untouched (never reconciled after the failure).
        assert app.state.db.list_active_rewards(user_id) == []


# ---- goals & lifestyle (user-onboarding) ---------------------------------


@pytest.mark.asyncio
async def test_onboarding_rejects_invalid_primary_goal(auth_client, app):
    """Spec: out-of-allowlist primary_goal -> 422 and nothing persists."""
    resp = await auth_client.post(
        "/api/onboarding", json=_payload(primary_goal="kettlebells")
    )
    assert resp.status_code == 422
    msgs = " ".join(str(e["msg"]) for e in resp.json()["detail"])
    assert "primary_goal" in msgs
    user_id = auth_user_id(app)
    assert _settings_count(app, user_id) == 0
    assert _weight_count(app, user_id) == 0


@pytest.mark.asyncio
async def test_onboarding_rejects_invalid_activity_level(auth_client, app):
    """Spec: out-of-allowlist activity_level -> 422 and nothing persists."""
    resp = await auth_client.post(
        "/api/onboarding", json=_payload(activity_level="extreme")
    )
    assert resp.status_code == 422
    msgs = " ".join(str(e["msg"]) for e in resp.json()["detail"])
    assert "activity_level" in msgs
    user_id = auth_user_id(app)
    assert _settings_count(app, user_id) == 0
    assert _weight_count(app, user_id) == 0


@pytest.mark.asyncio
async def test_settings_rejects_invalid_goals_preserves_current(auth_client, app):
    """Spec: an out-of-allowlist value via PUT /api/settings returns 422 and
    leaves the stored goals/lifestyle untouched."""
    user_id = auth_user_id(app)
    resp = await auth_client.post("/api/onboarding", json=_payload())
    assert resp.status_code == 200, resp.text
    rows_before = _settings_count(app, user_id)

    bad_goal = await auth_client.put(
        "/api/settings", json={"primary_goal": "crash_diet"}
    )
    assert bad_goal.status_code == 422
    bad_level = await auth_client.put(
        "/api/settings", json={"activity_level": "competitive"}
    )
    assert bad_level.status_code == 422

    # The rejected PUTs added/removed no settings rows.
    assert _settings_count(app, user_id) == rows_before
    settings = (await auth_client.get("/api/settings")).json()
    assert settings["primary_goal"] == "fitness"
    assert settings["secondary_goals"] == ["strength", "stamina"]
    assert settings["health_domains"] == ["nutrition", "sleep"]
    assert settings["activity_level"] == "moderate"


@pytest.mark.asyncio
async def test_goals_round_trip_per_user(pair, app):
    """Spec scenario: users A and B save different valid goals and lifestyle
    values; each reads back ONLY their own values with list order preserved.
    The settings PUT path round-trips the same JSON-list serialization."""
    alice, bob = pair

    alice_resp = await alice.post(
        "/api/onboarding",
        json=_payload(primary_goal="fitness",
                      secondary_goals=["strength", "stamina"],
                      health_domains=["nutrition", "sleep"],
                      activity_level="moderate"),
    )
    assert alice_resp.status_code == 200, alice_resp.text
    bob_resp = await bob.post(
        "/api/onboarding",
        json=_payload(primary_goal="weight_loss",
                      secondary_goals=["endurance"],
                      health_domains=["exercise"],
                      activity_level="active"),
    )
    assert bob_resp.status_code == 200, bob_resp.text

    alice_settings = (await alice.get("/api/settings")).json()
    assert alice_settings["primary_goal"] == "fitness"
    assert alice_settings["secondary_goals"] == ["strength", "stamina"]
    assert alice_settings["health_domains"] == ["nutrition", "sleep"]
    assert alice_settings["activity_level"] == "moderate"

    bob_settings = (await bob.get("/api/settings")).json()
    assert bob_settings["primary_goal"] == "weight_loss"
    assert bob_settings["secondary_goals"] == ["endurance"]
    assert bob_settings["health_domains"] == ["exercise"]
    assert bob_settings["activity_level"] == "active"

    # A later PUT overwrites one user's list and preserves the order given.
    updated = await bob.put(
        "/api/settings",
        json={"secondary_goals": ["cardio", "flexibility"],
              "health_domains": ["mindfulness"]},
    )
    assert updated.status_code == 200
    bob_settings = (await bob.get("/api/settings")).json()
    assert bob_settings["secondary_goals"] == ["cardio", "flexibility"]
    assert bob_settings["health_domains"] == ["mindfulness"]
    # Alice's values are untouched by Bob's write.
    alice_settings = (await alice.get("/api/settings")).json()
    assert alice_settings["secondary_goals"] == ["strength", "stamina"]
    assert alice_settings["health_domains"] == ["nutrition", "sleep"]


@pytest.mark.asyncio
async def test_onboarding_empty_lists_round_trip(auth_client, app):
    """Explicit empty lists persist as JSON and read back as [] (the empty
    list is a distinct serialization path from a populated list)."""
    user_id = auth_user_id(app)
    resp = await auth_client.post(
        "/api/onboarding",
        json=_payload(secondary_goals=[], health_domains=[]),
    )
    assert resp.status_code == 200, resp.text

    settings = (await auth_client.get("/api/settings")).json()
    assert settings["secondary_goals"] == []
    assert settings["health_domains"] == []
    assert settings["primary_goal"] == "fitness"
    # The stored rows hold the JSON form, not a Python repr.
    stored = {
        row["key"]: row["value"]
        for row in app.state.db.conn.execute(
            "SELECT key, value FROM settings WHERE user_id = ?", (user_id,)
        ).fetchall()
    }
    assert stored["secondary_goals"] == "[]"
    assert stored["health_domains"] == "[]"


@pytest.mark.asyncio
async def test_onboarding_omitted_goals_default(auth_client):
    """Omitting the optional goals/lifestyle fields yields the spec defaults:
    null, [], [], null (no settings rows are created for them)."""
    payload = _payload()
    for key in ("primary_goal", "secondary_goals", "health_domains",
                "activity_level"):
        payload.pop(key, None)
    resp = await auth_client.post("/api/onboarding", json=payload)
    assert resp.status_code == 200, resp.text

    settings = (await auth_client.get("/api/settings")).json()
    assert settings["primary_goal"] is None
    assert settings["secondary_goals"] == []
    assert settings["health_domains"] == []
    assert settings["activity_level"] is None
