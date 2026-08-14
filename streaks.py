"""Pure streak engine — no I/O, trivially unit-testable (mirrors rewards.py).

Streaks are derived, never persisted. Weekly streaks use ISO (year, week)
identity from ``date.isocalendar()``; the meal streak uses local calendar
days. Every period is walked backward from today: the current partial period
never breaks the streak, while a fully-elapsed period below its ``min_count``
stops the walk.
"""

from datetime import date, timedelta
from typing import Callable, Mapping, Sequence, TypeVar

from models import ExerciseEntry, MealEntry, StreakState, WeightEntry

Period = TypeVar("Period")


def prev_iso_week(week: tuple[int, int]) -> tuple[int, int]:
    """Previous ISO (year, week) tuple.

    Steps 7 days back from the given week's Monday and re-reads
    ``isocalendar()``, so the year-boundary rollover is handled correctly:
    ISO week 1 of year N+1 immediately follows week 52/53 of year N.
    """
    year, iso_week = week
    jan4 = date(year, 1, 4)
    monday_of_week_1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = monday_of_week_1 + timedelta(weeks=iso_week - 1)
    prev = (monday - timedelta(days=7)).isocalendar()
    return (prev.year, prev.week)


def _run_backward(
    counts: Mapping[Period, int],
    current: Period,
    prev_period: Callable[[Period], Period],
    min_count: int,
) -> int:
    """Consecutive periods ending at ``current`` with >= ``min_count`` rows.

    The current (partial) period never breaks the walk: it adds to the count
    only when it meets ``min_count`` and stays pending otherwise. Every
    fully-elapsed period below ``min_count`` stops the walk.
    """
    streak = 0
    period = current
    # The visited chain strictly decreases and every contributing step
    # consumes a distinct period present in `counts`, so this bound always
    # suffices: current (pending) + contributing periods + one breaking period.
    for _ in range(len(counts) + 2):
        if counts.get(period, 0) >= min_count:
            streak += 1
        elif period != current:
            break
        period = prev_period(period)
    return streak


def _counts_by_week(days: Sequence[date]) -> dict[tuple[int, int], int]:
    """Row counts per ISO (year, week) for the given dates."""
    counts: dict[tuple[int, int], int] = {}
    for day in days:
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _current_iso_week(today: date) -> tuple[int, int]:
    """ISO (year, week) tuple of the period containing ``today``."""
    iso = today.isocalendar()
    return (iso.year, iso.week)


def weight_streak(entries: Sequence[WeightEntry], today: date) -> int:
    """Consecutive ISO weeks ending at the current week with >= 1 entry."""
    days = [date.fromisoformat(entry.date) for entry in entries]
    return _run_backward(
        _counts_by_week(days), _current_iso_week(today), prev_iso_week, 1
    )


def exercise_streak(entries: Sequence[ExerciseEntry], today: date) -> int:
    """Consecutive ISO weeks ending at the current week with >= 3 rows each
    (row count, not distinct days)."""
    days = [date.fromisoformat(entry.date) for entry in entries]
    return _run_backward(
        _counts_by_week(days), _current_iso_week(today), prev_iso_week, 3
    )


def meal_streak(entries: Sequence[MealEntry], today: date) -> int:
    """Consecutive local days ending today with >= 1 meal entry."""
    counts: dict[date, int] = {}
    for entry in entries:
        day = date.fromisoformat(entry.date)
        counts[day] = counts.get(day, 0) + 1
    return _run_backward(counts, today, lambda d: d - timedelta(days=1), 1)


def first_run_milestones(
    days: Sequence[str], milestones: Sequence[int]
) -> dict[int, str]:
    """Earliest date each consecutive-day run first reaches a milestone
    length, keyed by milestone day-count (r2-completion · S4). Walks
    chronologically; a run is a maximal span of consecutive logged days and a
    missing day breaks it. The FIRST run reaching a milestone wins, so a
    29-day break before a later 30-day run earns the 30-day token on the later
    run's day 30, and later breaks never remove it (R13); only the given days
    count (weight/exercise streaks never feed meal milestones, R11)."""
    result: dict[int, str] = {}
    ordered = sorted({date.fromisoformat(day) for day in days})
    run_start = 0
    for index, day in enumerate(ordered):
        if index > run_start and (day - ordered[index - 1]).days != 1:
            run_start = index
        run_length = index - run_start + 1
        for milestone in milestones:
            if milestone not in result and run_length == milestone:
                result[milestone] = day.isoformat()
    return result


def streak_state(
    exercise: Sequence[ExerciseEntry],
    meals: Sequence[MealEntry],
    weights: Sequence[WeightEntry],
    today: date,
) -> StreakState:
    """Derive all three streaks from one user's histories and host-local today."""
    return StreakState(
        weight_weeks=weight_streak(weights, today),
        exercise_weeks=exercise_streak(exercise, today),
        meal_days=meal_streak(meals, today),
    )
