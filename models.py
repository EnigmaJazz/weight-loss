"""Dataclasses for the weight-loss tracker's structured state."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    salt: str
    created_at: str
    email: Optional[str] = None


@dataclass
class Session:
    id: int
    user_id: int
    token_hash: str
    created_at: str
    expires_at: str


@dataclass
class ResetToken:
    """A one-time password-reset token row; only the SHA-256 hash is stored."""

    id: int
    user_id: int
    token_hash: str
    created_at: str
    expires_at: str


@dataclass
class WeightEntry:
    id: int
    date: str
    weight_kg: float
    created_at: str
    time: Optional[str] = None


@dataclass
class ExerciseEntry:
    """One logged exercise row; multiple rows per user per date are allowed."""

    id: int
    date: str
    exercise_type: str
    duration_min: int
    created_at: str
    time: Optional[str] = None


@dataclass
class MealEntry:
    """One logged meal row; multiple rows per user per date are allowed."""

    id: int
    date: str
    calories: float
    created_at: str
    time: Optional[str] = None


@dataclass
class PushSubscription:
    id: int
    endpoint: str
    p256dh: str
    auth: str
    created_at: str


@dataclass
class ActiveCheckpoint:
    """One earned reward checkpoint (threshold reached by latest weight)."""

    percent: int
    threshold_kg: float
    earned_at: Optional[str] = None


@dataclass
class RewardState:
    """Derived checkpoint state for the latest weight against start/target."""

    start_kg: Optional[float] = None
    target_kg: Optional[float] = None
    current_kg: Optional[float] = None
    active: list[ActiveCheckpoint] = field(default_factory=list)
    earned_count: int = 0
    next_checkpoint: Optional[tuple[int, float]] = None
    progress_to_next: float = 0.0


@dataclass
class StreakState:
    """Derived stateless streak counts for one user (never persisted)."""

    weight_weeks: int = 0
    exercise_weeks: int = 0
    meal_days: int = 0


@dataclass
class WeightDisplay:
    """Typed multi-unit presentation of one weight value."""

    weight_kg: float
    lb: float
    stone: int
    stone_lb: float
    bmi: Optional[float]


@dataclass
class AppSettings:
    target_weight: Optional[float] = None
    target_bmi: Optional[float] = None  # BMI goal; resolved to kg on read
    tip_time: str = "09:00"
    reminder_time: str = "20:00"
    reminder_weekday: Optional[int] = 0  # Monday=0 ... Sunday=6
    exercise_time: str = "17:00"
    start_weight_override: Optional[float] = None
    height_cm: Optional[float] = None
    weight_unit: str = "kg"  # preferred input unit: "kg" | "st-lb"
    height_unit: str = "cm"  # preferred input unit: "cm" | "ft-in"
    target_unit: str = "kg"  # preferred target input unit: "kg" | "st-lb"
    weight_display: str = "lb"  # display preference: "lb" | "st-lb"
    theme: str = "system"  # per-user theme: "system" | "light" | "dark"
    onboarding_complete: bool = False  # wizard finished (flag lands Phase 3)

    def time_for(self, notif_type: str) -> str:
        """Scheduled "HH:MM" for a notification type ("" disables it)."""
        times = {
            "tip": self.tip_time,
            "reminder": self.reminder_time,
            "exercise": self.exercise_time,
        }
        return times.get(notif_type, "")

    def weekday_for(self, notif_type: str) -> Optional[int]:
        """Fixed weekday (0=Mon .. 6=Sun) for weekly types; None for daily."""
        if notif_type == "reminder":
            return self.reminder_weekday
        return None
