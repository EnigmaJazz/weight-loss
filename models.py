"""Dataclasses for the weight-loss tracker's structured state."""

from dataclasses import dataclass
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
class RewardMilestone:
    milestone_kg: float
    earned: bool
    earned_at: Optional[str]


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
    milestone_step_kg: float = 1.0
    tip_time: str = "09:00"
    reminder_time: str = "20:00"
    exercise_time: str = "17:00"
    start_weight_override: Optional[float] = None

    def time_for(self, notif_type: str) -> str:
        """Scheduled "HH:MM" for a notification type ("" disables it)."""
        times = {
            "tip": self.tip_time,
            "reminder": self.reminder_time,
            "exercise": self.exercise_time,
        }
        return times.get(notif_type, "")
