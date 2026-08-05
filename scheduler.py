"""Background scheduler: fires daily/weekly notifications once per period."""

import asyncio
from datetime import datetime
from typing import Any

from constants import (
    NOTIFICATION_MESSAGES,
    NOTIFICATION_TYPES,
    SCHEDULER_INTERVAL_SECONDS,
    get_logger,
)
from database import Database, run_db
import notifications

logger = get_logger("scheduler")


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _due_today(now: datetime, scheduled_time: str) -> bool:
    """True when the current time has reached the "HH:MM" schedule ("" = disabled)."""
    if not scheduled_time:
        return False
    return now.strftime("%H:%M") >= scheduled_time


def _due_this_week(now: datetime, scheduled_time: str, weekday: int | None) -> bool:
    """Weekly gate: time reached AND (no fixed weekday OR today is that weekday).
    Daily types pass weekday=None; weekly types require the matching weekday."""
    if not _due_today(now, scheduled_time):
        return False
    if weekday is None:
        return True
    return now.weekday() == weekday


async def run_due_checks(app_state: Any, now: datetime) -> int:
    """Send any notification types whose period has arrived. Returns count sent."""
    db: Database = app_state.db
    settings = await run_db(db.get_settings)
    today = now.date().isoformat()
    sent_count = 0
    for notif_type in NOTIFICATION_TYPES:
        if not _due_this_week(now, settings.time_for(notif_type), settings.weekday_for(notif_type)):
            continue
        if await run_db(db.is_notification_sent, today, notif_type):
            continue
        title, body = NOTIFICATION_MESSAGES[notif_type]
        subscriptions = await run_db(db.list_subscriptions)
        if not subscriptions:
            # Nothing was delivered, so do NOT consume the period's dedupe: a
            # send to zero subscribers is a no-op, and marking it sent would
            # silently skip the notification for the rest of the day once the
            # user enables push (reported: "timed notifications never fire").
            logger.info(
                "skipped %s notification for %s (no subscriptions)",
                notif_type,
                today,
            )
            continue
        await notifications.send_to_all(
            subscriptions, title, body, app_state.vapid, notif_type=notif_type
        )
        # Persist the tick's own local wall time (not a fresh now()) so sent_at
        # always matches the moment the schedule actually fired.
        await run_db(
            db.mark_notification_sent, today, notif_type, now.strftime("%Y-%m-%d %H:%M:%S")
        )
        sent_count += 1
        logger.info(
            "sent %s notification for %s (subscriptions: %d)",
            notif_type,
            today,
            len(subscriptions),
        )
    return sent_count


async def scheduler_loop(app_state: Any) -> None:
    """Long-running task started in lifespan. This loop boundary is allowed to
    catch broad exceptions so one bad tick never kills the scheduler."""
    while True:
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)
        try:
            await run_due_checks(app_state, datetime.now())
        except Exception:
            logger.exception("scheduler tick failed")
