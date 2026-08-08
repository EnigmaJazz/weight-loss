"""Tests for the scheduler's daily due-check + dedupe logic."""

from datetime import datetime

import pytest

from constants import NOTIFICATION_MESSAGES
import database as database_module
import notifications as notifications_module
from main import create_app, init_app_state
from scheduler import run_due_checks
from tests.conftest import auth_user_id

# Allowed titles come from the message pools so scheduler tests stay green as
# variants are added/rewritten (exact-title pins would break on any edit).
TIP_TITLES = {title for title, _ in NOTIFICATION_MESSAGES["tip"]}
REMINDER_TITLES = {title for title, _ in NOTIFICATION_MESSAGES["reminder"]}
EXERCISE_TITLES = {title for title, _ in NOTIFICATION_MESSAGES["exercise"]}


@pytest.mark.asyncio
async def test_due_checks_fire_once_then_dedupe(tmp_path, monkeypatch):
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        for sub in subscriptions:
            sent.append({"endpoint": sub.endpoint, "title": title})
        return len(sent)

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    user = _make_user(app.state.db, "tester")
    app.state.db.add_subscription(
        user.id, "https://push.example.com/sched", "p256dh-value", "auth-value"
    )

    # 09:30 on a default schedule: only the 09:00 tip is due.
    now = datetime(2026, 8, 2, 9, 30)
    count = await run_due_checks(app.state, now)
    assert count == 1
    assert len(sent) == 1
    assert app.state.db.is_notification_sent(user.id, "2026-08-02", "tip")
    assert not app.state.db.is_notification_sent(user.id, "2026-08-02", "reminder")

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

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        sent.append(title)
        return 1

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    user = _make_user(app.state.db, "tester")
    app.state.db.add_subscription(
        user.id, "https://push.example.com/sched", "p256dh-value", "auth-value"
    )

    # 10:00 on a default schedule: tip (09:00) due, reminder (20:00) and
    # exercise (17:00) not due yet.
    now = datetime(2026, 8, 2, 10, 0)
    count = await run_due_checks(app.state, now)
    assert count == 1
    assert len(sent) == 1

    # A disabled time (empty string) never fires.
    app.state.db.update_settings(user.id, {"tip_time": ""})
    sent.clear()
    app.state.db.mark_notification_sent(user.id, "2026-08-02", "tip")
    tomorrow = datetime(2026, 8, 3, 23, 59)
    count = await run_due_checks(app.state, tomorrow)
    # tip disabled -> only reminder (20:00) and exercise (17:00) fire at 23:59
    assert count == 2
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_due_checks_with_no_subscriptions(tmp_path, monkeypatch):
    calls = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        calls.append(len(subscriptions))
        return 0

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    user = _make_user(app.state.db, "tester")

    now = datetime(2026, 8, 2, 21, 0)  # tip, reminder, and exercise all due
    count = await run_due_checks(app.state, now)
    # Sending to zero subscribers is a no-op: it must NOT consume the day's
    # dedupe, otherwise the notification silently never fires once the user
    # enables push later that day.
    assert count == 0
    assert calls == []
    assert not app.state.db.is_notification_sent(user.id, "2026-08-02", "tip")


@pytest.mark.asyncio
async def test_due_checks_fires_after_subscriber_joins(tmp_path, monkeypatch):
    # Regression: a 09:00 tick with zero subscribers must not mark the day
    # sent; the same type fires later that day once a subscriber exists.
    calls = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        calls.append(len(subscriptions))
        return 0

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    user = _make_user(app.state.db, "tester")

    # First tick: tip due, no subscribers -> nothing sent, no dedupe.
    now = datetime(2026, 8, 2, 9, 0)
    count = await run_due_checks(app.state, now)
    assert count == 0
    assert not app.state.db.is_notification_sent(user.id, "2026-08-02", "tip")

    # User enables push: a subscription exists now.
    app.state.db.add_subscription(user.id, "https://fcm.example/abc", "k1", "k2")

    # Second tick same day: tip and exercise are still due, no dedupe exists
    # -> they fire. The weekly weigh-in reminder defaults to Monday; 2026-08-02
    # is a Sunday, so it stays silent (weekly gate).
    count = await run_due_checks(app.state, datetime(2026, 8, 2, 21, 0))
    assert count == 2  # tip + exercise (reminder not due on Sunday)
    assert calls == [1, 1]
    assert app.state.db.is_notification_sent(user.id, "2026-08-02", "tip")


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
    user = _make_user(app.state.db, "tester")
    app.state.db.add_subscription(user.id, "https://fcm.example/a", "k1", "k2")

    now = datetime(2026, 8, 2, 9, 30)
    count = await run_due_checks(app.state, now)
    assert count == 1

    with app.state.db._tx() as conn:
        row = conn.execute(
            "SELECT sent_at FROM notifications_sent"
            " WHERE user_id = ? AND date = ? AND type = ?",
            (user.id, "2026-08-02", "tip"),
        ).fetchone()
    assert row["sent_at"] == "2026-08-02 09:30:00"


@pytest.mark.asyncio
async def test_dst_repeated_hour_sends_once(tmp_path, monkeypatch):
    # Spec: a repeated wall-clock hour (fall-back) must yield at most one
    # scheduled attempt for that local date and type.
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        sent.append(title)
        return 1

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    user = _make_user(app.state.db, "tester")
    app.state.db.update_settings(user.id, {"tip_time": "01:00"})
    app.state.db.add_subscription(user.id, "https://fcm.example/a", "k1", "k2")

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

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        sent.append(title)
        return 1

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    user = _make_user(app.state.db, "tester")
    app.state.db.update_settings(user.id, {"exercise_time": "02:30"})
    app.state.db.add_subscription(user.id, "https://fcm.example/a", "k1", "k2")

    # 03:00 local: tip/reminder not due, the skipped 02:30 exercise IS due.
    now = datetime(2026, 3, 8, 3, 0)
    count = await run_due_checks(app.state, now)
    assert count == 1
    assert len(sent) == 1 and sent[0] in EXERCISE_TITLES
    assert app.state.db.is_notification_sent(user.id, "2026-03-08", "exercise")

    # And exercise stays deduped for the rest of that local date. The later
    # tick only adds tip (reminder is weekly and 2026-03-08 is a Sunday).
    count = await run_due_checks(app.state, datetime(2026, 3, 8, 23, 59))
    assert count == 1
    assert len(sent) == 2
    assert sent[0] in EXERCISE_TITLES  # the 03:00 exercise send, deduped here
    assert sent[1] in TIP_TITLES  # the later tick added only tip


# ---- notification-schedule-disable: full API -> scheduler path ----------


@pytest.mark.asyncio
async def test_api_disabled_schedule_is_skipped(auth_client, app, stub_push):
    # Spec: a type persisted as "" through PUT /api/settings must be skipped
    # by the scheduler at its former due time: zero sends, zero count, and no
    # (user, date, tip) dedupe key.
    await auth_client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://push.example.com/sched",
            "p256dh": "BEl62iUYgUivxIkv69yViEuiBIa_IbT8n1sWj3N5nPw",
            "auth": "F8UVa5fTzFQXlq6dZ0Gt7g",
        },
    )
    res = await auth_client.put("/api/settings", json={"tip_time": ""})
    assert res.status_code == 200
    assert res.json()["tip_time"] == ""
    user_id = auth_user_id(app)

    # 10:00: only tip (09:00) would be due; reminder (20:00) and exercise
    # (17:00) are not. Disabled tip -> nothing fires and nothing is marked.
    now = datetime(2026, 8, 2, 10, 0)
    count = await run_due_checks(app.state, now)
    assert count == 0
    assert stub_push == []
    assert not app.state.db.is_notification_sent(user_id, "2026-08-02", "tip")

    # Triangulate: re-enable tip through the API -> the same tick fires it,
    # proving the skip above came from the disable, not a broken scheduler.
    res = await auth_client.put("/api/settings", json={"tip_time": "09:00"})
    assert res.status_code == 200
    count = await run_due_checks(app.state, datetime(2026, 8, 2, 10, 0))
    assert count == 1
    assert len(stub_push) == 1
    assert app.state.db.is_notification_sent(user_id, "2026-08-02", "tip")


@pytest.mark.asyncio
async def test_weekly_reminder_fires_only_on_configured_weekday(tmp_path, monkeypatch):
    # Spec: the weigh-in reminder is weekly on a fixed weekday (reminder_weekday).
    # It must not fire on other weekdays even after its time has passed.
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        sent.append((notif_type, title))
        return 1

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    user = _make_user(app.state.db, "tester")
    app.state.db.update_settings(
        user.id, {"reminder_time": "09:00", "reminder_weekday": 1}
    )  # Tuesday
    app.state.db.add_subscription(user.id, "https://fcm.example/a", "k1", "k2")

    # Monday 09:30: reminder time passed but weekday does not match; tip (daily)
    # IS due and fires. The reminder must stay silent.
    monday = datetime(2026, 8, 3, 9, 30)
    assert monday.weekday() == 0
    count = await run_due_checks(app.state, monday)
    assert count == 1  # tip only
    assert len(sent) == 1
    assert sent[0][0] == "tip"
    assert sent[0][1] in TIP_TITLES
    assert not app.state.db.is_notification_sent(user.id, "2026-08-03", "reminder")

    # Tuesday 09:30: time passed AND weekday matches -> reminder fires (plus tip).
    tuesday = datetime(2026, 8, 4, 9, 30)
    assert tuesday.weekday() == 1
    count = await run_due_checks(app.state, tuesday)
    assert count == 2
    assert sent[-1][0] == "reminder"
    assert sent[-1][1] in REMINDER_TITLES
    assert app.state.db.is_notification_sent(user.id, "2026-08-04", "reminder")

    # Wednesday 09:30: next day, no dedupe for that date, but wrong weekday ->
    # only the daily tip fires; reminder stays silent again.
    wednesday = datetime(2026, 8, 5, 9, 30)
    assert wednesday.weekday() == 2
    count = await run_due_checks(app.state, wednesday)
    assert count == 1
    assert sent[-1][0] == "tip"
    assert sent[-1][1] in TIP_TITLES


# ---- per-user scheduling (user-accounts-auth, slice 2) -------------------


def _make_user(db, username):
    return db.create_user(username, "hash", "salt")


@pytest.mark.asyncio
async def test_per_user_dedupe_is_independent(tmp_path, monkeypatch):
    # Spec: two users with the same type due each receive their own send and
    # an independent dedupe key — user A's key must not suppress user B's.
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        for sub in subscriptions:
            sent.append(sub.endpoint)
        return len(sent)

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    alice = _make_user(app.state.db, "alice")
    bob = _make_user(app.state.db, "bob")
    app.state.db.add_subscription(
        alice.id, "https://push.example.com/alice", "k1", "k2"
    )
    app.state.db.add_subscription(
        bob.id, "https://push.example.com/bob", "k1", "k2"
    )

    now = datetime(2026, 8, 2, 9, 30)  # the 09:00 tip is due for both
    count = await run_due_checks(app.state, now)
    assert count == 2
    assert sorted(sent) == ["https://push.example.com/alice", "https://push.example.com/bob"]
    assert app.state.db.is_notification_sent(alice.id, "2026-08-02", "tip")
    assert app.state.db.is_notification_sent(bob.id, "2026-08-02", "tip")

    # A second pass is deduped for both users independently.
    count = await run_due_checks(app.state, now)
    assert count == 0
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_per_user_disabled_schedule_skips_only_that_user(tmp_path, monkeypatch):
    # Spec: user A disabling a type must not disable user B's schedule.
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        for sub in subscriptions:
            sent.append(sub.endpoint)
        return len(sent)

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    alice = _make_user(app.state.db, "alice")
    bob = _make_user(app.state.db, "bob")
    app.state.db.update_settings(alice.id, {"tip_time": ""})  # alice disables tip
    app.state.db.add_subscription(
        alice.id, "https://push.example.com/alice", "k1", "k2"
    )
    app.state.db.add_subscription(
        bob.id, "https://push.example.com/bob", "k1", "k2"
    )

    now = datetime(2026, 8, 2, 9, 30)
    count = await run_due_checks(app.state, now)
    assert count == 1  # only bob's tip fires
    assert sent == ["https://push.example.com/bob"]
    assert not app.state.db.is_notification_sent(alice.id, "2026-08-02", "tip")
    assert app.state.db.is_notification_sent(bob.id, "2026-08-02", "tip")


@pytest.mark.asyncio
async def test_per_user_zero_subscribers_consume_no_dedupe(tmp_path, monkeypatch):
    # Spec: a user with zero subscriptions must not consume that user's key;
    # a same-type due user with subscriptions still fires.
    sent = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        for sub in subscriptions:
            sent.append(sub.endpoint)
        return len(sent)

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)

    db_path = str(tmp_path / "sched.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    alice = _make_user(app.state.db, "alice")  # zero subscriptions
    bob = _make_user(app.state.db, "bob")
    app.state.db.add_subscription(
        bob.id, "https://push.example.com/bob", "k1", "k2"
    )

    now = datetime(2026, 8, 2, 9, 30)
    count = await run_due_checks(app.state, now)
    assert count == 1  # bob's tip fires; alice's zero-subscriber send is a no-op
    assert sent == ["https://push.example.com/bob"]
    assert not app.state.db.is_notification_sent(alice.id, "2026-08-02", "tip")
    assert app.state.db.is_notification_sent(bob.id, "2026-08-02", "tip")
