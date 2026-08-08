"""Integration tests: checkpoint celebration pushes (checkpoint-celebrations).

Earn events fire exactly ONE push naming the top newly-earned percent, tagged
notif_type="checkpoint", drawn from CELEBRATION_MESSAGES, and only to the
earning user's own subscriptions. No-fire mutations (idempotent re-POST,
revoke-only, failed edits, theme-only settings) never push. All pushes run
through the conftest stub_push, so nothing real is ever sent.

Threshold math used throughout: baseline 100 / target 80 -> 10% = 98,
25% = 95, 50% = 90.
"""

import pytest
from fastapi import FastAPI

import database as database_module
from constants import CELEBRATION_MESSAGES
from tests.conftest import auth_user_id, pair

SUBSCRIBE_BODY = {
    "endpoint": "https://push.example.com/v1/celebration",
    "p256dh": "BEl62iUYgUivxIkv69yViEuiBIa_IbT8n1sWj3N5nPw",
    "auth": "F8UVa5fTzFQXlq6dZ0Gt7g",
}


def _assert_celebration(push: dict[str, str], percent: int) -> None:
    """The recorded push is a valid celebration naming ``percent`` exactly."""
    assert push["notif_type"] == "checkpoint"
    assert "{percent}" not in push["title"] + push["body"]
    assert f"{percent}%" in push["title"] + push["body"]
    assert any(
        push["title"] == title.replace("{percent}", str(percent))
        and push["body"] == body.replace("{percent}", str(percent))
        for title, body in CELEBRATION_MESSAGES
    )


async def _put_settings(client, **updates) -> None:
    resp = await client.put("/api/settings", json=updates)
    assert resp.status_code == 200, resp.text


async def _post_weight(client, date: str, weight_kg: float) -> int:
    resp = await client.post("/api/weight", json={"date": date, "weight_kg": weight_kg})
    assert resp.status_code in (200, 201), resp.text  # 201 new, 200 idempotent re-POST
    return resp.json()["id"]


async def _subscribe(client, endpoint: str = SUBSCRIBE_BODY["endpoint"]) -> None:
    body = dict(SUBSCRIBE_BODY, endpoint=endpoint)
    resp = await client.post("/api/push/subscribe", json=body)
    assert resp.status_code == 201, resp.text


# ---- upsert earn -----------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_single_earn_fires_one_push_naming_10(auth_client, stub_push):
    # Spec: baseline 100, current reaches 98 -> exactly one push naming 10.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _subscribe(auth_client)

    await _post_weight(auth_client, "2026-08-02", 98.0)

    assert len(stub_push) == 1
    _assert_celebration(stub_push[0], 10)


@pytest.mark.asyncio
async def test_upsert_batched_earn_fires_one_push_naming_top(auth_client, stub_push):
    # Spec: {10, 25, 50} newly earned in one upsert -> ONE push naming 50.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _subscribe(auth_client)

    await _post_weight(auth_client, "2026-08-02", 90.0)

    assert len(stub_push) == 1
    _assert_celebration(stub_push[0], 50)


@pytest.mark.asyncio
async def test_idempotent_repost_no_fire(auth_client, stub_push):
    # Spec: re-POSTing the same weight -> before == after -> zero pushes.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _subscribe(auth_client)
    await _post_weight(auth_client, "2026-08-02", 90.0)
    assert len(stub_push) == 1

    await _post_weight(auth_client, "2026-08-02", 90.0)

    assert len(stub_push) == 1


@pytest.mark.asyncio
async def test_revoke_only_no_fire(auth_client, stub_push):
    # Spec: regressing above every threshold revokes -> zero pushes.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _subscribe(auth_client)
    await _post_weight(auth_client, "2026-08-02", 90.0)
    assert len(stub_push) == 1

    await _post_weight(auth_client, "2026-08-03", 99.0)

    assert len(stub_push) == 1


@pytest.mark.asyncio
async def test_reearn_after_regression_fires_again(auth_client, stub_push, monkeypatch):
    # Spec: 25% earned, revoked, then recovered -> fires again (fresh earned_at).
    monkeypatch.setattr(database_module, "_local_now", lambda: "2026-08-04 12:00:00")
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _subscribe(auth_client)
    await _post_weight(auth_client, "2026-08-02", 90.0)
    assert len(stub_push) == 1  # {10, 25, 50}
    await _post_weight(auth_client, "2026-08-03", 99.0)  # revoke everything
    assert len(stub_push) == 1

    await _post_weight(auth_client, "2026-08-04", 94.0)  # recover past 95

    assert len(stub_push) == 2
    _assert_celebration(stub_push[1], 25)


# ---- edit earn -------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_earn_fires(auth_client, stub_push):
    # Spec: editing a weight past the 50% threshold -> one push naming 50.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    entry_id = await _post_weight(auth_client, "2026-08-02", 99.0)
    await _subscribe(auth_client)
    assert stub_push == []

    resp = await auth_client.put(
        f"/api/weight/{entry_id}",
        json={"date": "2026-08-02", "weight_kg": 90.0},
    )
    assert resp.status_code == 200

    assert len(stub_push) == 1
    _assert_celebration(stub_push[0], 50)


@pytest.mark.asyncio
async def test_edit_409_no_fire(auth_client, stub_push):
    # Spec: date collision raises 409 BEFORE celebrate -> zero pushes.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    entry_id = await _post_weight(auth_client, "2026-08-02", 98.0)
    await _subscribe(auth_client)
    assert stub_push == []

    resp = await auth_client.put(
        f"/api/weight/{entry_id}",
        json={"date": "2026-08-01", "weight_kg": 90.0},  # collides with 08-01
    )
    assert resp.status_code == 409

    assert stub_push == []


# ---- delete earn -----------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_baseline_shift_earn_fires(auth_client, stub_push, app):
    # Spec: deleting the earliest entry shifts the baseline 80 -> 100 and earns
    # {10, 25, 50} against current 90 -> one push naming 50.
    await _put_settings(auth_client, target_weight=80.0)
    baseline_id = await _post_weight(auth_client, "2026-08-01", 80.0)
    await _post_weight(auth_client, "2026-08-02", 100.0)
    await _post_weight(auth_client, "2026-08-03", 90.0)
    await _subscribe(auth_client)
    assert stub_push == []

    resp = await auth_client.delete(f"/api/weight/{baseline_id}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    assert len(stub_push) == 1
    _assert_celebration(stub_push[0], 50)
    assert app.state.db.list_active_rewards(auth_user_id(app))  # sanity: earned


@pytest.mark.asyncio
async def test_delete_revoke_only_no_fire(auth_client, stub_push):
    # Spec: deleting the latest entry revokes {10, 25} -> zero pushes.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    latest_id = await _post_weight(auth_client, "2026-08-02", 95.0)
    await _subscribe(auth_client)
    assert stub_push == []

    resp = await auth_client.delete(f"/api/weight/{latest_id}")
    assert resp.status_code == 200

    assert stub_push == []


# ---- settings earn ---------------------------------------------------------


@pytest.mark.asyncio
async def test_settings_target_earn_fires(auth_client, stub_push):
    # Spec: a target change that newly earns 50% -> one push naming 50.
    await _put_settings(auth_client, height_cm=175.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _post_weight(auth_client, "2026-08-02", 90.0)
    await _subscribe(auth_client)
    assert stub_push == []

    await _put_settings(auth_client, target_weight=80.0)

    assert len(stub_push) == 1
    _assert_celebration(stub_push[0], 50)


@pytest.mark.asyncio
async def test_settings_theme_only_no_fire(auth_client, stub_push):
    # Spec: a theme-only settings update fires zero pushes even when checkpoints
    # are active and the user is subscribed.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _subscribe(auth_client)
    await _post_weight(auth_client, "2026-08-02", 90.0)
    assert len(stub_push) == 1

    await _put_settings(auth_client, theme="dark")

    assert len(stub_push) == 1


# ---- onboarding earn -------------------------------------------------------


@pytest.mark.asyncio
async def test_onboarding_first_entry_earn_fires(auth_client, stub_push):
    # Spec: onboarding's first weight (with a pre-set baseline override) earns
    # {10, 25, 50} -> exactly one push naming the top percent.
    await _put_settings(auth_client, start_weight_override=100.0, target_weight=80.0)
    await _subscribe(auth_client)
    assert stub_push == []

    resp = await auth_client.post(
        "/api/onboarding",
        json={
            "height_cm": 175.0,
            "weight_kg": 90.0,
            "target_weight": 80.0,
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    assert len(stub_push) == 1
    _assert_celebration(stub_push[0], 50)


# ---- no-fire and isolation guards ------------------------------------------


@pytest.mark.asyncio
async def test_zero_subscriptions_no_fire_no_dedupe(auth_client, stub_push, app):
    # Spec: an earn with zero subscriptions attempts zero pushes and writes no
    # notifications_sent dedupe row.
    await _put_settings(auth_client, target_weight=80.0)
    await _post_weight(auth_client, "2026-08-01", 100.0)
    await _post_weight(auth_client, "2026-08-02", 90.0)
    assert stub_push == []

    rows = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM notifications_sent"
    ).fetchone()
    assert rows is not None
    assert rows[0] == 0


@pytest.mark.asyncio
async def test_per_user_isolation(pair, stub_push):
    # Spec: alice's earn notifies only alice's own subscriptions; bob's
    # subscription is never touched even though he is subscribed.
    alice, bob = pair
    await _put_settings(alice, target_weight=80.0)
    await _post_weight(alice, "2026-08-01", 100.0)
    await _subscribe(alice, endpoint="https://push.example.com/alice")
    await _subscribe(bob, endpoint="https://push.example.com/bob")

    await _post_weight(alice, "2026-08-02", 90.0)

    assert len(stub_push) == 1
    assert stub_push[0]["endpoint"] == "https://push.example.com/alice"
    _assert_celebration(stub_push[0], 50)
