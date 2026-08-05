"""Tests for the scheduler's daily due-check + dedupe logic."""

from datetime import datetime

import pytest

import database as database_module
import notifications as notifications_module
from main import create_app, init_app_state
from scheduler import run_due_checks


@pytest.mark.asyncio
async def test_due_checks_fire_once_then_dedupe(tmp_path, monkeypatch):
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid):
        for sub in subscriptions:
            sent.append({"endpoint": sub.endpoint, "title": title})
        return len(sent)

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    app.state.db.add_subscription(
        "https://push.example.com/sched", "p256dh-value", "auth-value"
    )

    # 09:30 on a default schedule: only the 09:00 tip is due.
    now = datetime(2026, 8, 2, 9, 30)
    count = await run_due_checks(app.state, now)
    assert count == 1
    assert len(sent) == 1
    assert app.state.db.is_notification_sent("2026-08-02", "tip")
    assert not app.state.db.is_notification_sent("2026-08-02", "reminder")

    # Second pass the same day: deduped, nothing new sent.
    count = await run_due_checks(app.state, now)
    assert count == 0
    assert len(sent) == 1

    # Next day the same time fires again.
    next_day = datetime(2026, 8, 3, 9, 30)
    count = await run_due_checks(app.state, next_day)
    assert count == 1
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_due_checks_respects_scheduled_times(tmp_path, monkeypatch):
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid):
        sent.append(title)
        return 1

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    app.state.db.add_subscription(
        "https://push.example.com/sched", "p256dh-value", "auth-value"
    )

    # 10:00 on a default schedule: tip (09:00) due, reminder (20:00) and
    # exercise (17:00) not due yet.
    now = datetime(2026, 8, 2, 10, 0)
    count = await run_due_checks(app.state, now)
    assert count == 1
    assert len(sent) == 1

    # A disabled time (empty string) never fires.
    app.state.db.update_settings({"tip_time": ""})
    sent.clear()
    app.state.db.mark_notification_sent("2026-08-02", "tip")
    tomorrow = datetime(2026, 8, 3, 23, 59)
    count = await run_due_checks(app.state, tomorrow)
    # tip disabled -> only reminder (20:00) and exercise (17:00) fire at 23:59
    assert count == 2
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_due_checks_with_no_subscriptions(tmp_path, monkeypatch):
    calls = []

    async def fake_send_to_all(subscriptions, title, body, vapid):
        calls.append(len(subscriptions))
        return 0

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)

    now = datetime(2026, 8, 2, 21, 0)  # tip, reminder, and exercise all due
    count = await run_due_checks(app.state, now)
    assert count == 3
    assert calls == [0, 0, 0]
    # Still marked sent so the type fires once per day regardless.
    assert app.state.db.is_notification_sent("2026-08-02", "tip")


# ---- 2.2: local-time sent_at + DST day semantics ------------------------


@pytest.mark.asyncio
async def test_scheduler_persists_sent_at_from_tick(tmp_path, monkeypatch):
    # Spec: scheduled-send sent_at MUST be the host-local wall time of the
    # event — the scheduler's own tick, not an unrelated fresh now().
    monkeypatch.setattr(
        database_module, "_local_now", lambda: "1999-01-01 00:00:00"
    )

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)

    now = datetime(2026, 8, 2, 9, 30)
    count = await run_due_checks(app.state, now)
    assert count == 1

    with app.state.db._tx() as conn:
        row = conn.execute(
            "SELECT sent_at FROM notifications_sent WHERE date = ? AND type = ?",
            ("2026-08-02", "tip"),
        ).fetchone()
    assert row["sent_at"] == "2026-08-02 09:30:00"


@pytest.mark.asyncio
async def test_dst_repeated_hour_sends_once(tmp_path, monkeypatch):
    # Spec: a repeated wall-clock hour (fall-back) must yield at most one
    # scheduled attempt for that local date and type.
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid):
        sent.append(title)
        return 1

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    app.state.db.update_settings({"tip_time": "01:00"})

    repeated_hour = datetime(2026, 11, 1, 1, 30)  # first occurrence
    count = await run_due_checks(app.state, repeated_hour)
    assert count == 1
    assert len(sent) == 1

    second_occurrence = datetime(2026, 11, 1, 1, 30)
    count = await run_due_checks(app.state, second_occurrence)
    assert count == 0
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_dst_skipped_time_fires_on_next_tick(tmp_path, monkeypatch):
    # Spec: a wall-clock time skipped by a forward transition fires on the
    # next scheduler check on that local date when no key exists yet.
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid):
        sent.append(title)
        return 1

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    app.state.db.update_settings({"exercise_time": "02:30"})

    # 03:00 local: tip/reminder not due, the skipped 02:30 exercise IS due.
    now = datetime(2026, 3, 8, 3, 0)
    count = await run_due_checks(app.state, now)
    assert count == 1
    assert sent == ["Exercise encouragement"]
    assert app.state.db.is_notification_sent("2026-03-08", "exercise")

    # And exercise stays deduped for the rest of that local date (the later
    # ticks only add tip/reminder, which were never sent that day).
    count = await run_due_checks(app.state, datetime(2026, 3, 8, 23, 59))
    assert count == 2
    assert sent.count("Exercise encouragement") == 1


# ---- notification-schedule-disable: full API -> scheduler path ----------


@pytest.mark.asyncio
async def test_api_disabled_schedule_is_skipped(client, app, stub_push):
    # Spec: a type persisted as "" through PUT /api/settings must be skipped
    # by the scheduler at its former due time: zero sends, zero count, and no
    # (date, tip) dedupe key.
    await client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://push.example.com/sched",
            "p256dh": "BEl62iUYgUivxIkv69yViEuiBIa_IbT8n1sWj3N5nPw",
            "auth": "F8UVa5fTzFQXlq6dZ0Gt7g",
        },
    )
    res = await client.put("/api/settings", json={"tip_time": ""})
    assert res.status_code == 200
    assert res.json()["tip_time"] == ""

    # 10:00: only tip (09:00) would be due; reminder (20:00) and exercise
    # (17:00) are not. Disabled tip -> nothing fires and nothing is marked.
    now = datetime(2026, 8, 2, 10, 0)
    count = await run_due_checks(app.state, now)
    assert count == 0
    assert stub_push == []
    assert not app.state.db.is_notification_sent("2026-08-02", "tip")

    # Triangulate: re-enable tip through the API -> the same tick fires it,
    # proving the skip above came from the disable, not a broken scheduler.
    res = await client.put("/api/settings", json={"tip_time": "09:00"})
    assert res.status_code == 200
    count = await run_due_checks(app.state, datetime(2026, 8, 2, 10, 0))
    assert count == 1
    assert len(stub_push) == 1
    assert app.state.db.is_notification_sent("2026-08-02", "tip")
