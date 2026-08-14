"""Pure weekly-objectives engine — no I/O, trivially unit-testable (mirrors
rewards.py/momentum.py/streaks.py).

Each Monday–Sunday week tracks two objectives — 10 done quests and 3
successful momentum days (Good/Great only; Spark and unclassified days never
count) — and pays a 40-XP award exactly once per met (user, week, objective).
Activation is forward-only: a partial activation week (mid-week activation) is
exempt and the following Monday begins the first counted week. database.py
gathers week facts and persists awards; this module never touches storage.
"""

from datetime import date, timedelta
from typing import Sequence

from models import MomentumDayFacts, WeeklyGoalState, WeeklySnapshot
from momentum import classify_day, is_successful

# The two weekly objectives in response order; targets are exact counts.
WEEK_GOALS: tuple[str, ...] = ("quests", "good_days")
WEEK_TARGETS: dict[str, int] = {"quests": 10, "good_days": 3}
WEEK_AWARD_XP: int = 40


def week_start(day: date) -> date:
    """The Monday of the Monday–Sunday week containing ``day`` (ISO-year
    rollover is implicit: weekday arithmetic crosses year boundaries)."""
    return day - timedelta(days=day.weekday())


def goal_met(goal: str, current: int) -> bool:
    """Whether ``current`` reaches the objective's exact target."""
    return current >= WEEK_TARGETS[goal]


def week_count(snapshot: WeeklySnapshot, goal: str) -> int:
    """The raw count for ``goal`` from a week snapshot: done quests or
    successful days."""
    return snapshot.done_quests if goal == "quests" else snapshot.good_days


def goal_state(goal: str, current: int, awarded: bool) -> WeeklyGoalState:
    """One objective's response state: current count, exact target, met-ness,
    and whether the 40-XP award is already persisted for the week."""
    return WeeklyGoalState(
        goal=goal,
        current=current,
        target=WEEK_TARGETS[goal],
        met=goal_met(goal, current),
        awarded=awarded,
    )


def good_day_count(days: Sequence[MomentumDayFacts], week: date) -> int:
    """Good/Great days inside the week starting ``week`` (momentum
    ``is_successful`` semantics): Spark days and days with no current
    assignment never count; dates outside the week and dates without facts
    resolve to unclassified and count zero."""
    by_date = {fact.date: fact for fact in days}
    successful = 0
    for offset in range(7):
        day = (week + timedelta(days=offset)).isoformat()
        facts = by_date.get(day, MomentumDayFacts(date=day))
        if is_successful(classify_day(facts)):
            successful += 1
    return successful


def first_counted_week(activation: date) -> date:
    """The Monday of the first week eligible for awards. Activation on the
    Monday boundary starts a full week (counted); activation after a Monday
    begins leaves a partial week (exempt) and the next Monday starts the
    first counted week (R7)."""
    if activation.weekday() == 0:
        return activation
    return week_start(activation) + timedelta(days=7)


def is_counted_week(week: date, activation: date) -> bool:
    """Whether the week starting ``week`` may earn XP for a user activated on
    ``activation`` (forward-only: pre-activation and partial weeks never do)."""
    return week >= first_counted_week(activation)
