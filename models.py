"""Dataclasses for the weight-loss tracker's structured state."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WeightEntry:
    id: int
    date: str
    weight_kg: float
    created_at: str


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
    tip_time: str = "09:00"
    reminder_time: str = "20:00"
    reminder_weekday: Optional[int] = 0  # Monday=0 ... Sunday=6
    exercise_time: str = "17:00"
    start_weight_override: Optional[float] = None
    height_cm: Optional[float] = None

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
