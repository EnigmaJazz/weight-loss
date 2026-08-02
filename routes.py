"""HTTP API routes for the weight-loss tracker."""

from dataclasses import asdict
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from constants import (
    NOTIFICATION_MESSAGES,
    NOTIFICATION_TYPES,
    TEST_NOTIFICATION_BODY,
    TEST_NOTIFICATION_TITLE,
    get_logger,
)
from database import Database, run_db
from models import WeightEntry
import notifications
from rewards import (
    compute_baseline,
    compute_current,
    compute_lost,
    remaining_to_target,
    reward_state,
)

router = APIRouter()
logger = get_logger("routes")


async def get_db(request: Request) -> Database:
    return request.app.state.db


# ---- request bodies -----------------------------------------------------


def _valid_date(value: str) -> str:
    from datetime import date

    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be in YYYY-MM-DD format") from exc
    return value


def _valid_time(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    parts = value.split(":")
    if len(parts) != 2 or not all(p.isdigit() and len(p) == 2 for p in parts):
        raise ValueError('time must be in "HH:MM" format')
    hour, minute = (int(p) for p in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time out of range")
    return f"{hour:02d}:{minute:02d}"


class WeightIn(BaseModel):
    date: str
    weight_kg: float = Field(gt=0)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return _valid_date(value)


class PushSubscribeIn(BaseModel):
    endpoint: str
    p256dh: str
    auth: str

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("endpoint must be a valid http(s) URL")
        return value

    @field_validator("p256dh", "auth")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not value:
            raise ValueError("key must not be empty")
        return value


class PushUnsubscribeIn(BaseModel):
    endpoint: str

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("endpoint must be a valid http(s) URL")
        return value


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_weight: Optional[float] = Field(default=None, gt=0)
    tip_time: Optional[str] = None
    reminder_time: Optional[str] = None
    exercise_time: Optional[str] = None
    start_weight_override: Optional[float] = Field(default=None, gt=0)
    height_cm: Optional[float] = Field(default=None, gt=0)

    @field_validator("tip_time", "reminder_time", "exercise_time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        return _valid_time(value)


# ---- serialization ------------------------------------------------------


def _entry_dict(entry: WeightEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "date": entry.date,
        "weight_kg": entry.weight_kg,
        "created_at": entry.created_at,
    }


# ---- weight -------------------------------------------------------------


@router.get("/api/weight")
async def get_weight(db: Database = Depends(get_db)) -> dict[str, Any]:
    entries = await run_db(db.list_entries)
    settings = await run_db(db.get_settings)
    baseline = compute_baseline(entries, settings.start_weight_override)
    current = compute_current(entries)
    lost = compute_lost(baseline, current)
    summary = {
        "baseline_kg": baseline,
        "current_kg": current,
        "lost_kg": lost,
        "target_kg": settings.target_weight,
        "remaining_kg": remaining_to_target(current, settings.target_weight),
    }
    return {"entries": [_entry_dict(e) for e in entries], "summary": summary}


@router.post("/api/weight")
async def upsert_weight(
    payload: WeightIn, db: Database = Depends(get_db)
) -> JSONResponse:
    existing = await run_db(db.get_entry_by_date, payload.date)
    entry = await run_db(db.upsert_entry, payload.date, payload.weight_kg)
    status_code = 200 if existing is not None else 201
    return JSONResponse(status_code=status_code, content=_entry_dict(entry))


@router.delete("/api/weight/{entry_id}")
async def delete_weight(
    entry_id: int, db: Database = Depends(get_db)
) -> dict[str, bool]:
    deleted = await run_db(db.delete_entry, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"deleted": True}


# ---- rewards ------------------------------------------------------------


@router.get("/api/rewards")
async def get_rewards(db: Database = Depends(get_db)) -> dict[str, Any]:
    entries = await run_db(db.list_entries)
    settings = await run_db(db.get_settings)
    earned_rows = await run_db(db.list_active_rewards)
    state = reward_state(entries, settings)
    earned_at_by_percent = {
        row["checkpoint_percent"]: row["earned_at"] for row in earned_rows
    }
    active_checkpoints = [
        {
            "percent": cp.percent,
            "threshold_kg": cp.threshold_kg,
            "earned_at": earned_at_by_percent.get(cp.percent),
        }
        for cp in state.active
    ]
    nxt = state.next_checkpoint
    return {
        "active_checkpoints": active_checkpoints,
        "earned_count": state.earned_count,
        "next_checkpoint": (
            {"percent": nxt[0], "threshold_kg": nxt[1]} if nxt is not None else None
        ),
        "progress_to_next": state.progress_to_next,
    }


# ---- settings -----------------------------------------------------------


@router.get("/api/settings")
async def get_settings(db: Database = Depends(get_db)) -> dict[str, Any]:
    settings = await run_db(db.get_settings)
    return asdict(settings)


@router.put("/api/settings")
async def put_settings(
    payload: SettingsIn, db: Database = Depends(get_db)
) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if updates:
        await run_db(db.update_settings, updates)
    settings = await run_db(db.get_settings)
    return asdict(settings)


# ---- push notifications -------------------------------------------------


@router.get("/api/push/vapid-public-key")
async def vapid_public_key(request: Request) -> dict[str, str]:
    return {"public_key": request.app.state.vapid_public_key}


@router.post("/api/push/subscribe", status_code=201)
async def push_subscribe(
    payload: PushSubscribeIn, db: Database = Depends(get_db)
) -> dict[str, Any]:
    subscription = await run_db(
        db.add_subscription, payload.endpoint, payload.p256dh, payload.auth
    )
    logger.info("subscribed push endpoint %s", payload.endpoint)
    return {"id": subscription.id, "endpoint": subscription.endpoint}


@router.post("/api/push/unsubscribe")
async def push_unsubscribe(
    payload: PushUnsubscribeIn, db: Database = Depends(get_db)
) -> dict[str, bool]:
    removed = await run_db(db.remove_subscription, payload.endpoint)
    if removed:
        logger.info("unsubscribed push endpoint %s", payload.endpoint)
    return {"removed": removed}


@router.post("/api/push/test")
async def push_test(
    request: Request, db: Database = Depends(get_db)
) -> dict[str, int]:
    subscriptions = await run_db(db.list_subscriptions)
    sent = await notifications.send_to_all(
        subscriptions, TEST_NOTIFICATION_TITLE, TEST_NOTIFICATION_BODY, request.app.state.vapid
    )
    return {"sent": sent, "total": len(subscriptions)}


@router.post("/api/notify/{notif_type}")
async def notify_manual(
    notif_type: str, request: Request, db: Database = Depends(get_db)
) -> dict[str, int]:
    if notif_type not in NOTIFICATION_TYPES:
        raise HTTPException(status_code=404, detail="unknown notification type")
    subscriptions = await run_db(db.list_subscriptions)
    title, body = NOTIFICATION_MESSAGES[notif_type]
    sent = await notifications.send_to_all(
        subscriptions, title, body, request.app.state.vapid
    )
    return {"sent": sent, "total": len(subscriptions)}
