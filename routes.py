"""HTTP API routes for the weight-loss tracker."""

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from auth import (
    generate_password_salt,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from constants import (
    NOTIFICATION_MESSAGES,
    NOTIFICATION_TYPES,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_EXPIRY_SECONDS,
    TEST_NOTIFICATION_BODY,
    TEST_NOTIFICATION_TITLE,
    get_logger,
)
from database import Database, DuplicateUsernameError, run_db
from models import User, WeightEntry
import notifications
from rewards import (
    compute_baseline,
    compute_current,
    compute_lost,
    remaining_to_target,
    reward_state,
)
from units import weight_display

router = APIRouter()
logger = get_logger("routes")


async def get_db(request: Request) -> Database:
    return request.app.state.db


async def require_user(
    request: Request, db: Database = Depends(get_db)
) -> User:
    """Resolve the session cookie to a User, or raise 401.

    Missing, unknown, and expired sessions are all treated identically:
    401, never 403, so no information about session state leaks.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    user = await run_db(db.get_user_by_session, hash_session_token(token))
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


# ---- authentication ----------------------------------------------------


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not (3 <= len(normalized) <= 32):
            raise ValueError("username must be 3-32 characters")
        if any(ch.isspace() for ch in normalized):
            raise ValueError("username must not contain whitespace")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        return value


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


# ---- request bodies -----------------------------------------------------


def _valid_date(value: str) -> str:
    from datetime import date

    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must be in YYYY-MM-DD format") from exc
    return value


def _valid_time(value: Optional[str]) -> Optional[str]:
    """Validate a notification schedule time.

    Accepts strict "HH:MM" for enabled schedules, "" as the disabled
    sentinel (persisted unchanged), and None (JSON null) as the
    restore-default operation that removes the override.
    """
    if not value:
        return value
    parts = value.split(":")
    if len(parts) != 2 or not all(p.isdigit() and len(p) == 2 for p in parts):
        raise ValueError('time must be in "HH:MM" format')
    hour, minute = (int(p) for p in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time out of range")
    return f"{hour:02d}:{minute:02d}"


class WeightIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    reminder_weekday: Optional[int] = Field(default=None, ge=0, le=6)
    exercise_time: Optional[str] = None
    start_weight_override: Optional[float] = Field(default=None, gt=0)
    height_cm: Optional[float] = Field(default=None, gt=0)

    @field_validator("tip_time", "reminder_time", "exercise_time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        return _valid_time(value)


# ---- serialization ------------------------------------------------------


def _weight_view(
    weight_kg: Optional[float], height_cm: Optional[float]
) -> dict[str, Any]:
    """Raw derived display values (lb/stone/stone_lb/bmi) for one weight;
    None-safe so the SPA just formats without null-guarding every field."""
    if weight_kg is None:
        return {"lb": None, "stone": None, "stone_lb": None, "bmi": None}
    display = weight_display(weight_kg, height_cm)
    return {
        "lb": display.lb,
        "stone": display.stone,
        "stone_lb": display.stone_lb,
        "bmi": display.bmi,
    }


def _entry_dict(entry: WeightEntry, height_cm: Optional[float]) -> dict[str, Any]:
    view = _weight_view(entry.weight_kg, height_cm)
    return {
        "id": entry.id,
        "date": entry.date,
        "weight_kg": entry.weight_kg,
        "lb": view["lb"],
        "stone": view["stone"],
        "stone_lb": view["stone_lb"],
        "bmi": view["bmi"],
        "created_at": entry.created_at,
    }


def _summary_view(
    entries: list[WeightEntry], settings: Any, height_cm: Optional[float]
) -> dict[str, Any]:
    """Summary dict: canonical *_kg keys plus raw multi-unit siblings.
    BMI rides along on real weights (baseline/current/target) but not on
    deltas (lost/remaining), where it would be meaningless."""
    baseline = compute_baseline(entries, settings.start_weight_override)
    current = compute_current(entries)
    target = settings.target_weight
    values = (
        ("baseline", baseline),
        ("current", current),
        ("lost", compute_lost(baseline, current)),
        ("target", target),
        ("remaining", remaining_to_target(current, target)),
    )
    summary: dict[str, Any] = {}
    for name, value in values:
        summary[f"{name}_kg"] = value
        view = _weight_view(value, height_cm)
        summary[f"{name}_lb"] = view["lb"]
        summary[f"{name}_stone"] = view["stone"]
        summary[f"{name}_stone_lb"] = view["stone_lb"]
        if name in ("baseline", "current", "target"):
            summary[f"{name}_bmi"] = view["bmi"]
    return summary


# ---- auth helpers ------------------------------------------------------


def _user_view(user: User) -> dict[str, Any]:
    """Public identity fields only — never password_hash or salt."""
    return {
        "id": user.id,
        "username": user.username,
        "created_at": user.created_at,
    }


def _session_expiry() -> datetime:
    """UTC instant 30 days from now; DB row and cookie share it."""
    return datetime.now(timezone.utc) + timedelta(seconds=SESSION_EXPIRY_SECONDS)


def _set_session_cookie(
    response: Response, token: str, expires_at: datetime
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_EXPIRY_SECONDS,
        expires=expires_at,
        path=SESSION_COOKIE_PATH,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
        secure=SESSION_COOKIE_SECURE,
    )


async def _establish_session(
    response: Response, db: Database, user: User
) -> None:
    """Create a session row and stamp its token on the response cookie."""
    token = generate_session_token()
    expires_at = _session_expiry()
    await run_db(
        db.create_session,
        user.id,
        hash_session_token(token),
        expires_at.strftime("%Y-%m-%d %H:%M:%S"),
    )
    _set_session_cookie(response, token, expires_at)


# ---- authentication routes ----------------------------------------------


@router.post("/api/auth/register", status_code=201)
async def register(
    payload: RegisterIn,
    response: Response,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    salt = generate_password_salt()
    password_hash = await asyncio.to_thread(hash_password, payload.password, salt)
    try:
        user = await run_db(db.create_user, payload.username, password_hash, salt)
    except DuplicateUsernameError:
        raise HTTPException(status_code=409, detail="username already taken")
    await _establish_session(response, db, user)
    logger.info("registered user %s", user.username)
    return _user_view(user)


@router.post("/api/auth/login")
async def login(
    payload: LoginIn,
    response: Response,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    user = await run_db(db.get_user_by_username, payload.username)
    if user is None or not await asyncio.to_thread(
        verify_password, payload.password, user.salt, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="invalid username or password")
    await _establish_session(response, db, user)
    logger.info("logged in user %s", user.username)
    return _user_view(user)


@router.get("/api/auth/me")
async def me(user: User = Depends(require_user)) -> dict[str, Any]:
    return _user_view(user)


@router.post("/api/auth/logout")
async def logout(
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, bool]:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    await run_db(db.delete_session, hash_session_token(token))
    response.delete_cookie(SESSION_COOKIE_NAME, path=SESSION_COOKIE_PATH)
    logger.info("logged out user %s", user.username)
    return {"ok": True}


# ---- weight -------------------------------------------------------------


@router.get("/api/weight")
async def get_weight(
    user: User = Depends(require_user), db: Database = Depends(get_db)
) -> dict[str, Any]:
    entries = await run_db(db.list_entries, user.id)
    settings = await run_db(db.get_settings, user.id)
    summary = _summary_view(entries, settings, settings.height_cm)
    return {
        "entries": [_entry_dict(e, settings.height_cm) for e in entries],
        "summary": summary,
    }


@router.post("/api/weight")
async def upsert_weight(
    payload: WeightIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> JSONResponse:
    existing = await run_db(db.get_entry_by_date, user.id, payload.date)
    entry = await run_db(db.upsert_entry, user.id, payload.date, payload.weight_kg)
    settings = await run_db(db.get_settings, user.id)
    status_code = 200 if existing is not None else 201
    return JSONResponse(
        status_code=status_code, content=_entry_dict(entry, settings.height_cm)
    )


@router.delete("/api/weight/{entry_id}")
async def delete_weight(
    entry_id: int,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, bool]:
    # Ownership is enforced in the DELETE (WHERE id AND user_id): a cross-user
    # id deletes nothing and surfaces as 404, leaking no information.
    deleted = await run_db(db.delete_entry, user.id, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"deleted": True}


# ---- rewards ------------------------------------------------------------


@router.get("/api/rewards")
async def get_rewards(
    user: User = Depends(require_user), db: Database = Depends(get_db)
) -> dict[str, Any]:
    entries = await run_db(db.list_entries, user.id)
    settings = await run_db(db.get_settings, user.id)
    earned_rows = await run_db(db.list_active_rewards, user.id)
    state = reward_state(entries, settings)
    earned_at_by_percent = {
        row["checkpoint_percent"]: row["earned_at"] for row in earned_rows
    }
    active_checkpoints = []
    for cp in state.active:
        view = _weight_view(cp.threshold_kg, settings.height_cm)
        active_checkpoints.append(
            {
                "percent": cp.percent,
                "threshold_kg": cp.threshold_kg,
                "threshold_lb": view["lb"],
                "threshold_stone": view["stone"],
                "threshold_stone_lb": view["stone_lb"],
                "earned_at": earned_at_by_percent.get(cp.percent),
            }
        )
    nxt = state.next_checkpoint
    if nxt is not None:
        view = _weight_view(nxt[1], settings.height_cm)
        next_checkpoint = {
            "percent": nxt[0],
            "threshold_kg": nxt[1],
            "threshold_lb": view["lb"],
            "threshold_stone": view["stone"],
            "threshold_stone_lb": view["stone_lb"],
        }
    else:
        next_checkpoint = None
    return {
        "active_checkpoints": active_checkpoints,
        "earned_count": state.earned_count,
        "next_checkpoint": next_checkpoint,
        "progress_to_next": state.progress_to_next,
    }


# ---- settings -----------------------------------------------------------


@router.get("/api/settings")
async def get_settings(
    user: User = Depends(require_user), db: Database = Depends(get_db)
) -> dict[str, Any]:
    settings = await run_db(db.get_settings, user.id)
    return asdict(settings)


@router.put("/api/settings")
async def put_settings(
    payload: SettingsIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if updates:
        await run_db(db.update_settings, user.id, updates)
    settings = await run_db(db.get_settings, user.id)
    return asdict(settings)


# ---- push notifications -------------------------------------------------


@router.get("/api/push/vapid-public-key")
async def vapid_public_key(request: Request) -> dict[str, str]:
    return {"public_key": request.app.state.vapid_public_key}


@router.post("/api/push/subscribe", status_code=201)
async def push_subscribe(
    payload: PushSubscribeIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    subscription = await run_db(
        db.add_subscription, user.id, payload.endpoint, payload.p256dh, payload.auth
    )
    logger.info("subscribed push endpoint %s", payload.endpoint)
    return {"id": subscription.id, "endpoint": subscription.endpoint}


@router.post("/api/push/unsubscribe")
async def push_unsubscribe(
    payload: PushUnsubscribeIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, bool]:
    removed = await run_db(db.remove_subscription, user.id, payload.endpoint)
    if removed:
        logger.info("unsubscribed push endpoint %s", payload.endpoint)
    return {"removed": removed}


@router.post("/api/push/test")
async def push_test(
    request: Request,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, int]:
    subscriptions = await run_db(db.list_subscriptions, user.id)
    sent = await notifications.send_to_all(
        subscriptions, TEST_NOTIFICATION_TITLE, TEST_NOTIFICATION_BODY, request.app.state.vapid
    )
    return {"sent": sent, "total": len(subscriptions)}


@router.post("/api/notify/{notif_type}")
async def notify_manual(
    notif_type: str,
    request: Request,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, int]:
    if notif_type not in NOTIFICATION_TYPES:
        raise HTTPException(status_code=404, detail="unknown notification type")
    subscriptions = await run_db(db.list_subscriptions, user.id)
    title, body = NOTIFICATION_MESSAGES[notif_type]
    sent = await notifications.send_to_all(
        subscriptions, title, body, request.app.state.vapid
    )
    return {"sent": sent, "total": len(subscriptions)}
