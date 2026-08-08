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
    """A fully valid onboarding payload; overrides replace fields."""
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
        "/api/onboarding", json=_payload(weight_unit="st-lb")
    )
    assert third.status_code == 200
    assert _settings_count(app, user_id) == rows_before
    settings = (await auth_client.get("/api/settings")).json()
    assert settings["weight_unit"] == "st-lb"
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
