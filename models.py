"""Dataclasses for the weight-loss tracker's structured state."""

from dataclasses import dataclass, field
from typing import Any, Optional


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
class MoodEntry:
    """One logged mood check-in row; multiple rows per user per date are
    allowed. ``mood`` is an integer from 1 through 5 and ``note`` an optional
    free-text field of at most 500 characters (both validated in routes.py)."""

    id: int
    date: str
    mood: int
    created_at: str
    note: Optional[str] = None
    time: Optional[str] = None


@dataclass
class HabitEntry:
    """One logged habit check-in row from the fixed v1 catalogue; multiple
    rows per user per date are allowed."""

    id: int
    date: str
    habit_type: str
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
    # Goals & lifestyle (user-onboarding): all optional. Lists round-trip as
    # JSON (order preserved); primary_goal and activity_level are allowlisted
    # in constants.py and validated in routes.py.
    primary_goal: Optional[str] = None
    secondary_goals: list[str] = field(default_factory=list)
    health_domains: list[str] = field(default_factory=list)
    activity_level: Optional[str] = None

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


@dataclass
class Quest:
    """One persisted daily quest row (owner id omitted, entry-style)."""

    id: int
    date: str
    quest_key: str
    domain: str
    title: str
    description: str
    xp_value: int
    status: str
    difficulty: str
    source: str
    created_at: str
    completed_at: Optional[str] = None


@dataclass
class QuestDetectionFacts:
    """Detection-relevant facts for one user+date gathered from the log
    tables. has_mood/has_habit come from the mood/habit tables (S3); the
    habit side is HABIT_TYPES-driven — only catalogue habit rows qualify."""

    date: str
    has_weight: bool = False
    exercise_min: int = 0
    has_meal: bool = False
    has_mood: bool = False
    has_habit: bool = False
    has_any_entry: bool = False


@dataclass
class XpState:
    """Derived XP state for one user (never persisted), mirroring the
    derived-not-persisted pattern of StreakState/RewardState."""

    level: int
    title: str
    total_xp: int
    xp_into_next: int
    next_level_at: int


@dataclass
class MomentumDayFacts:
    """Per-date momentum facts for one user gathered from the quest and log
    tables. ``assigned_quests`` counts current assignments (replaced rows are
    not current); ``done_quests`` counts done quests; ``log_rows`` counts the
    user's weight/exercise/meal/mood/habit rows for the date."""

    date: str
    assigned_quests: int = 0
    done_quests: int = 0
    log_rows: int = 0


@dataclass
class MomentumState:
    """Derived 21-day momentum state for one user (never persisted), mirroring
    the derived-not-persisted pattern of StreakState/RewardState."""

    today_tier: str
    successful_days: int
    window_days: int
    is_successful_today: bool


@dataclass
class AchievementQuestFact:
    """One done quest row for the achievements engine (date = quest.date)."""

    date: str
    quest_key: str
    domain: str


@dataclass
class ExerciseDayFacts:
    """One user's summed exercise minutes for one local date."""

    date: str
    duration_min: int = 0


@dataclass
class AchievementFacts:
    """Facts the pure achievements engine consumes: one per-user snapshot
    gathered in a single database read (never persisted)."""

    done_quests: list[AchievementQuestFact] = field(default_factory=list)
    momentum_days: list[MomentumDayFacts] = field(default_factory=list)
    exercise_days: list[ExerciseDayFacts] = field(default_factory=list)


@dataclass
class AchievementState:
    """One derived achievement state (never persisted)."""

    key: str
    title: str
    earned: bool
    unlocked_at: Optional[str] = None


@dataclass
class WeeklySnapshot:
    """One user's per-week facts gathered in a single transaction (never
    persisted): done quests, successful days, and goals already paid."""

    week: str  # ISO date of the week's Monday
    done_quests: int = 0
    good_days: int = 0
    awarded: set[str] = field(default_factory=set)


@dataclass
class WeeklyGoalState:
    """One weekly objective's derived status for the API surface."""

    goal: str
    current: int
    target: int
    met: bool
    awarded: bool


@dataclass
class WeeklyState:
    """The full GET /api/weekly response state for one user (never persisted):
    activation stamp, current-week progress, bounded 12-week history, and the
    goals newly paid by the read that produced it."""

    activation: Optional[str]
    current_week: str
    exempt: bool
    goals: list[WeeklyGoalState]
    history: list[dict[str, Any]]
    met_flips: list[str]
