"""Background scheduler: fires daily notifications once per type per day."""

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


def _due_today(now: datetime, scheduled_time: str) -> bool:
    """True when the current time has reached the "HH:MM" schedule ("" = disabled)."""
    if not scheduled_time:
        return False
    return now.strftime("%H:%M") >= scheduled_time


async def run_due_checks(app_state: Any, now: datetime) -> int:
    """Send any notification types whose time has passed today. Returns count sent."""
    db: Database = app_state.db
    settings = await run_db(db.get_settings)
    today = now.date().isoformat()
    sent_count = 0
    for notif_type in NOTIFICATION_TYPES:
        if not _due_today(now, settings.time_for(notif_type)):
            continue
        if await run_db(db.is_notification_sent, today, notif_type):
            continue
        title, body = NOTIFICATION_MESSAGES[notif_type]
        subscriptions = await run_db(db.list_subscriptions)
        await notifications.send_to_all(subscriptions, title, body, app_state.vapid)
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
