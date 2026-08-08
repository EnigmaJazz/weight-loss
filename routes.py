"""HTTP API routes for the weight-loss tracker."""

import asyncio
import re
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

import mailer
from auth import (
    generate_password_salt,
    generate_reset_token,
    generate_session_token,
    hash_password,
    hash_reset_token,
    hash_session_token,
    verify_password,
)
from constants import (
    EXERCISE_TYPES,
    NOTIFICATION_TYPES,
    PUBLIC_URL,
    RESET_TOKEN_EXPIRY_SECONDS,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    SESSION_EXPIRY_SECONDS,
    TEST_NOTIFICATION_BODY,
    TEST_NOTIFICATION_TITLE,
    get_logger,
)
from database import (
    Database,
    DuplicateDateError,
    DuplicateEmailError,
    DuplicateUsernameError,
    run_db,
)
from models import ExerciseEntry, MealEntry, User, WeightEntry
import notifications
from rewards import (
    compute_baseline,
    compute_current,
    compute_lost,
    remaining_to_target,
    reward_state,
)
from streaks import streak_state
from units import (
    calculate_bmi,
    classify_bmi,
    healthy_weight_range,
    resolve_target_kg,
    weight_display,
)

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

# Basic email format check shared by every validator that accepts an email:
# local@domain.tld with no spaces. Normalization (strip + lowercase) happens
# here too so storage, lookup, and the client mirror the username pattern.
_EMAIL_MAX_LENGTH = 254
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) > _EMAIL_MAX_LENGTH or not _EMAIL_RE.match(normalized):
        raise ValueError("email must be a valid address")
    return normalized


def _valid_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    return value


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str
    email: str

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
        return _valid_password(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _valid_email(value)


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class EmailIn(BaseModel):
    """Body for PUT /api/auth/me — set or update the account email."""

    model_config = ConfigDict(extra="forbid")

    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _valid_email(value)


class ForgotPasswordIn(BaseModel):
    """Body for POST /api/auth/forgot-password — an account email."""

    model_config = ConfigDict(extra="forbid")

    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _valid_email(value)


class ResetPasswordIn(BaseModel):
    """Body for POST /api/auth/reset-password — a one-time token + new password."""

    model_config = ConfigDict(extra="forbid")

    token: str
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _valid_password(value)


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


def _valid_activity_time(value: Optional[str]) -> Optional[str]:
    """Validate an optional activity time-of-day.

    Accepts strict "HH:MM" (24h) or empty/None, which both normalize to None
    ("no time"). Unlike schedule times, "" is NOT a disabled sentinel here.
    """
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 2 or not all(p.isdigit() and len(p) == 2 for p in parts):
        raise ValueError("time must be in HH:MM format")
    hour, minute = (int(p) for p in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time must be in HH:MM format")
    return f"{hour:02d}:{minute:02d}"


class WeightIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    weight_kg: float = Field(gt=0)
    time: Optional[str] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return _valid_date(value)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        return _valid_activity_time(value)


class ExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    time: Optional[str] = None
    exercise_type: str
    duration_min: int = Field(gt=0)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return _valid_date(value)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        return _valid_activity_time(value)

    @field_validator("exercise_type")
    @classmethod
    def validate_exercise_type(cls, value: str) -> str:
        if value not in EXERCISE_TYPES:
            raise ValueError("unknown exercise_type")
        return value


class MealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    time: Optional[str] = None
    calories: float = Field(gt=0)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return _valid_date(value)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        return _valid_activity_time(value)


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
    target_bmi: Optional[float] = Field(default=None, gt=10, le=40)
    tip_time: Optional[str] = None
    reminder_time: Optional[str] = None
    reminder_weekday: Optional[int] = Field(default=None, ge=0, le=6)
    exercise_time: Optional[str] = None
    start_weight_override: Optional[float] = Field(default=None, gt=0)
    height_cm: Optional[float] = Field(default=None, gt=0)
    weight_unit: Optional[str] = None  # "kg" | "st-lb"
    height_unit: Optional[str] = None  # "cm" | "ft-in"
    target_unit: Optional[str] = None  # "kg" | "st-lb"
    weight_display: Optional[str] = None  # "lb" | "st-lb"

    @field_validator("tip_time", "reminder_time", "exercise_time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        return _valid_time(value)

    @field_validator("weight_unit", "target_unit")
    @classmethod
    def validate_weight_unit(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ("kg", "st-lb"):
            raise ValueError('unit must be "kg" or "st-lb"')
        return value

    @field_validator("height_unit")
    @classmethod
    def validate_height_unit(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ("cm", "ft-in"):
            raise ValueError('height_unit must be "cm" or "ft-in"')
        return value

    @field_validator("weight_display")
    @classmethod
    def validate_weight_display(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ("lb", "st-lb"):
            raise ValueError('weight_display must be "lb" or "st-lb"')
        return value


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
        "time": entry.time,
        "weight_kg": entry.weight_kg,
        "lb": view["lb"],
        "stone": view["stone"],
        "stone_lb": view["stone_lb"],
        "bmi": view["bmi"],
        "created_at": entry.created_at,
    }


def _exercise_dict(entry: ExerciseEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "date": entry.date,
        "time": entry.time,
        "exercise_type": entry.exercise_type,
        "duration_min": entry.duration_min,
        "created_at": entry.created_at,
    }


def _meal_dict(entry: MealEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "date": entry.date,
        "time": entry.time,
        "calories": entry.calories,
        "created_at": entry.created_at,
    }


def _summary_view(
    entries: list[WeightEntry], settings: Any, height_cm: Optional[float]
) -> dict[str, Any]:
    """Summary dict: canonical *_kg keys plus raw multi-unit siblings.
    BMI rides along on real weights (baseline/current/target) but not on
    deltas (lost/remaining), where it would be meaningless. The target is the
    shared resolved kg (target_weight precedence over target_bmi), so summary
    and rewards can never disagree. The healthy range and target status ride
    along too, null when height (or target, for status) is unset."""
    baseline = compute_baseline(entries, settings.start_weight_override)
    current = compute_current(entries)
    target = resolve_target_kg(
        settings.target_weight, settings.target_bmi, settings.height_cm
    )
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
    healthy = healthy_weight_range(height_cm)
    summary["healthy_min_kg"] = healthy[0] if healthy is not None else None
    summary["healthy_max_kg"] = healthy[1] if healthy is not None else None
    status_bmi = calculate_bmi(target, height_cm) if target is not None else None
    summary["target_status"] = (
        classify_bmi(status_bmi) if status_bmi is not None else None
    )
    return summary


# ---- auth helpers ------------------------------------------------------


def _user_view(user: User) -> dict[str, Any]:
    """Public identity fields only — never password_hash or salt."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
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
        user = await run_db(
            db.create_user, payload.username, password_hash, salt, payload.email
        )
    except DuplicateUsernameError:
        raise HTTPException(status_code=409, detail="username already taken")
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="email already in use")
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


@router.put("/api/auth/me")
async def update_me(
    payload: EmailIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """Set or update the authenticated account's email (required for accounts
    created before registration collected one).

    The address must not already belong to another account: account recovery
    is only safe when an email has exactly one owner."""
    try:
        updated = await run_db(db.set_user_email, user.id, payload.email)
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="email already in use")
    logger.info("updated email for user %s", user.username)
    return _user_view(updated)


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


@router.post("/api/auth/forgot-password")
async def forgot_password(
    payload: ForgotPasswordIn,
    db: Database = Depends(get_db),
) -> dict[str, str]:
    """Issue a one-time reset token and email its link.

    Always returns 200 with the same generic message whether or not the email
    is registered, so the endpoint never reveals account existence (no user
    enumeration). When SMTP is unconfigured or delivery fails, the raw token
    is logged as a dev fallback instead of the request failing.
    """
    user = await run_db(db.get_user_by_email, payload.email)
    if user is not None:
        token = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=RESET_TOKEN_EXPIRY_SECONDS
        )
        await run_db(
            db.create_reset_token,
            user.id,
            hash_reset_token(token),
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        reset_url = f"{PUBLIC_URL}/?reset={token}"
        sent = await asyncio.to_thread(
            mailer.send_reset_email, payload.email, reset_url
        )
        if not sent:
            # SMTP unconfigured or delivery failed: keep the flow working in
            # dev; the operator recovers the link from this log line.
            logger.warning(
                "password reset email not sent to %s; dev fallback token: %s",
                payload.email,
                token,
            )
    return {"message": "If that email exists, a reset link is on its way"}


@router.post("/api/auth/reset-password")
async def reset_password(
    payload: ResetPasswordIn,
    db: Database = Depends(get_db),
) -> dict[str, str]:
    """Set a new password with a one-time reset token.

    Missing, expired, and already-used tokens are all rejected identically
    (422). A successful reset rotates the scrypt hash/salt, consumes the
    token, and revokes every session for the account atomically.
    """
    token_hash = hash_reset_token(payload.token)
    user = await run_db(db.get_user_by_reset_token, token_hash)
    if user is None:
        raise HTTPException(status_code=422, detail="invalid or expired reset token")
    salt = generate_password_salt()
    password_hash = await asyncio.to_thread(hash_password, payload.password, salt)
    await run_db(
        db.reset_user_password, user.id, password_hash, salt, token_hash
    )
    logger.info("password reset for user %s", user.username)
    return {"message": "password reset — you can log in now"}


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
    entry = await run_db(
        db.upsert_entry, user.id, payload.date, payload.weight_kg, payload.time
    )
    settings = await run_db(db.get_settings, user.id)
    status_code = 200 if existing is not None else 201
    return JSONResponse(
        status_code=status_code, content=_entry_dict(entry, settings.height_cm)
    )


@router.put("/api/weight/{entry_id}")
async def edit_weight(
    entry_id: int,
    payload: WeightIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    # Ownership + date-conflict checks live in update_entry: a cross-user id
    # surfaces as 404 (checked first), and moving onto another entry's date
    # surfaces as 409 rather than silently overwriting that day's weight.
    try:
        entry = await run_db(
            db.update_entry,
            user.id,
            entry_id,
            payload.date,
            payload.weight_kg,
            payload.time,
        )
    except DuplicateDateError:
        raise HTTPException(status_code=409, detail="date already has an entry")
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    settings = await run_db(db.get_settings, user.id)
    logger.info("updated weight for user %s", user.username)
    return _entry_dict(entry, settings.height_cm)


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


# ---- activity logging: exercise and meal entries ---------------------------


@router.get("/api/exercise")
async def get_exercise(
    user: User = Depends(require_user), db: Database = Depends(get_db)
) -> dict[str, Any]:
    entries = await run_db(db.list_exercise, user.id)
    return {"entries": [_exercise_dict(e) for e in entries]}


@router.post("/api/exercise", status_code=201)
async def add_exercise(
    payload: ExerciseIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    entry = await run_db(
        db.insert_exercise,
        user.id,
        payload.date,
        payload.exercise_type,
        payload.duration_min,
        payload.time,
    )
    logger.info(
        "logged %s exercise for user %s", payload.exercise_type, user.username
    )
    return _exercise_dict(entry)


@router.put("/api/exercise/{entry_id}")
async def edit_exercise(
    entry_id: int,
    payload: ExerciseIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    # Ownership is enforced in the UPDATE (WHERE id AND user_id): a cross-user
    # id updates nothing and surfaces as 404, leaking no information.
    entry = await run_db(
        db.update_exercise,
        user.id,
        entry_id,
        payload.date,
        payload.time,
        payload.exercise_type,
        payload.duration_min,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    logger.info(
        "updated %s exercise for user %s", payload.exercise_type, user.username
    )
    return _exercise_dict(entry)


@router.delete("/api/exercise/{entry_id}")
async def delete_exercise(
    entry_id: int,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, bool]:
    # Ownership is enforced in the DELETE (WHERE id AND user_id): a cross-user
    # id deletes nothing and surfaces as 404, leaking no information.
    deleted = await run_db(db.delete_exercise, user.id, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"deleted": True}


@router.get("/api/meals")
async def get_meals(
    user: User = Depends(require_user), db: Database = Depends(get_db)
) -> dict[str, Any]:
    entries = await run_db(db.list_meals, user.id)
    return {"entries": [_meal_dict(e) for e in entries]}


@router.post("/api/meals", status_code=201)
async def add_meal(
    payload: MealIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    entry = await run_db(
        db.insert_meal, user.id, payload.date, payload.calories, payload.time
    )
    logger.info("logged meal for user %s", user.username)
    return _meal_dict(entry)


@router.put("/api/meals/{entry_id}")
async def edit_meal(
    entry_id: int,
    payload: MealIn,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    # Ownership is enforced in the UPDATE (WHERE id AND user_id): a cross-user
    # id updates nothing and surfaces as 404, leaking no information.
    entry = await run_db(
        db.update_meal,
        user.id,
        entry_id,
        payload.date,
        payload.time,
        payload.calories,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="entry not found")
    logger.info("updated meal for user %s", user.username)
    return _meal_dict(entry)


@router.delete("/api/meals/{entry_id}")
async def delete_meal(
    entry_id: int,
    user: User = Depends(require_user),
    db: Database = Depends(get_db),
) -> dict[str, bool]:
    # Ownership is enforced in the DELETE (WHERE id AND user_id): a cross-user
    # id deletes nothing and surfaces as 404, leaking no information.
    deleted = await run_db(db.delete_meal, user.id, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"deleted": True}


# ---- streaks -------------------------------------------------------------


@router.get("/api/streaks")
async def get_streaks(
    user: User = Depends(require_user), db: Database = Depends(get_db)
) -> dict[str, Any]:
    """Derive all three streaks from this user's histories — never persisted.

    The engine walks backward from the host-local today: the current partial
    period stays pending, a fully-elapsed empty period breaks the streak.
    """
    exercise = await run_db(db.list_exercise, user.id)
    meals = await run_db(db.list_meals, user.id)
    weights = await run_db(db.list_entries, user.id)
    state = streak_state(exercise, meals, weights, date.today())
    return asdict(state)


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
        # The resolved target that drives the thresholds — identical to the
        # summary's target_kg by construction (same resolve_target_kg helper).
        "target_kg": state.target_kg,
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
    # Design AD2 — bidirectional target clearing: saving one target form nulls
    # the other, so the two persisted targets can never diverge. (A null save
    # is a clear operation, not a switch, so it leaves the other target alone.)
    # When both are supplied in one payload, target_weight wins — matching the
    # shared resolver's documented precedence.
    if updates.get("target_weight") is not None:
        updates["target_bmi"] = None
    if updates.get("target_bmi") is not None:
        updates["target_weight"] = None
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
    title, body = notifications.pick_message(notif_type)
    sent = await notifications.send_to_all(
        subscriptions, title, body, request.app.state.vapid, notif_type=notif_type
    )
    return {"sent": sent, "total": len(subscriptions)}
