"""Tests for the scheduler's daily due-check + dedupe logic."""

from datetime import datetime

import pytest

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
