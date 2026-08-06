"""Unit tests for the pure streak engine (streaks.py) — work unit 1.

Covers the activity-logging spec scenarios: empty->0, single->1, gap break,
pending partial periods (weight 1 / exercise 2-vs-3 / meal), multi-meal one
day, ISO year-boundary rollover, and deletion changing the next read.
"""

from datetime import date, timedelta

from models import ExerciseEntry, MealEntry, StreakState, WeightEntry
from streaks import (
    exercise_streak,
    meal_streak,
    prev_iso_week,
    streak_state,
    weight_streak,
)

# A mid-week reference "today": the current period is partial, never elapsed.
TODAY = date(2026, 7, 22)


def _monday_of_iso_week(year: int, week: int) -> date:
    """Monday of the given ISO (year, week)."""
    jan4 = date(year, 1, 4)
    monday_of_week_1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    return monday_of_week_1 + timedelta(weeks=week - 1)


def _week_monday(weeks_back: int) -> date:
    """Monday of the ISO week `weeks_back` before the week containing TODAY."""
    iso = TODAY.isocalendar()
    return _monday_of_iso_week(iso.year, iso.week - weeks_back)


def _weight(day: date) -> WeightEntry:
    return WeightEntry(id=1, date=day.isoformat(), weight_kg=80.0,
                       created_at="2026-01-01T09:00:00")


def _exercise(day: date) -> ExerciseEntry:
    return ExerciseEntry(id=1, date=day.isoformat(), exercise_type="walk",
                         duration_min=30, created_at="2026-01-01T09:00:00")


def _meal(day: date) -> MealEntry:
    return MealEntry(id=1, date=day.isoformat(), calories=500.0,
                     created_at="2026-01-01T09:00:00")


class TestPrevIsoWeek:
    def test_within_year_step(self) -> None:
        assert prev_iso_week((2026, 2)) == (2026, 1)

    def test_year_boundary_rollover(self) -> None:
        # ISO 2027-W1 (Jan 4-10, 2027) follows 2026-W53 (Dec 28, 2026 - Jan 3).
        assert prev_iso_week((2027, 1)) == (2026, 53)

    def test_other_year_boundary(self) -> None:
        # ISO 2026-W1 starts Dec 29, 2025; the week before is 2025-W52.
        assert prev_iso_week((2026, 1)) == (2025, 52)


class TestWeightStreak:
    def test_empty_history_yields_zero(self) -> None:
        assert weight_streak([], TODAY) == 0

    def test_single_entry_counts_as_one(self) -> None:
        entries = [_weight(_week_monday(0))]
        assert weight_streak(entries, TODAY) == 1

    def test_gap_week_breaks_streak(self) -> None:
        # Current week and W-2 have entries; fully-elapsed W-1 has none.
        entries = [_weight(_week_monday(0)), _weight(_week_monday(2))]
        assert weight_streak(entries, TODAY) == 1

    def test_empty_current_week_stays_pending(self) -> None:
        # Five fully-elapsed weeks with entries, none this week: 5, not 6.
        entries = [_weight(_week_monday(back)) for back in range(1, 6)]
        assert weight_streak(entries, TODAY) == 5

    def test_deletion_changes_next_read(self) -> None:
        # Three consecutive weeks read as 3; dropping the current-week entry
        # leaves the current week pending and reduces the read to 2.
        entries = [_weight(_week_monday(back)) for back in range(3)]
        assert weight_streak(entries, TODAY) == 3
        reduced = [entry for entry in entries if entry.date != _week_monday(0).isoformat()]
        assert weight_streak(reduced, TODAY) == 2

    def test_iso_year_boundary_preserves_continuity(self) -> None:
        # 2026-12-28 is 2026-W53; 2027-01-04 is 2027-W1. No gap -> streak 2.
        entries = [_weight(date(2026, 12, 28)), _weight(date(2027, 1, 4))]
        assert weight_streak(entries, date(2027, 1, 4)) == 2


class TestExerciseStreak:
    def test_empty_history_yields_zero(self) -> None:
        assert exercise_streak([], TODAY) == 0

    def test_single_row_below_threshold_stays_pending(self) -> None:
        # 1 row this week < 3: pending, and no prior weeks -> 0.
        entries = [_exercise(_week_monday(0))]
        assert exercise_streak(entries, TODAY) == 0

    def test_third_row_in_current_week_extends(self) -> None:
        # Prior 1-week streak (W-1, 3 rows) plus exactly 3 rows this week -> 2.
        entries = [_exercise(_week_monday(0)) for _ in range(3)]
        entries += [_exercise(_week_monday(1)) for _ in range(3)]
        assert exercise_streak(entries, TODAY) == 2

    def test_two_rows_keep_it_pending(self) -> None:
        # Prior 1-week streak (W-1, 3 rows), only 2 rows this week -> 1.
        entries = [_exercise(_week_monday(0)) for _ in range(2)]
        entries += [_exercise(_week_monday(1)) for _ in range(3)]
        assert exercise_streak(entries, TODAY) == 1

    def test_elapsed_week_under_three_breaks(self) -> None:
        # 3 rows current week and W-2, but only 1 in fully-elapsed W-1 -> 1.
        entries = [_exercise(_week_monday(0)) for _ in range(3)]
        entries += [_exercise(_week_monday(1))]
        entries += [_exercise(_week_monday(2)) for _ in range(3)]
        assert exercise_streak(entries, TODAY) == 1


class TestMealStreak:
    def test_empty_history_yields_zero(self) -> None:
        assert meal_streak([], TODAY) == 0

    def test_single_meal_today_counts_as_one(self) -> None:
        assert meal_streak([_meal(TODAY)], TODAY) == 1

    def test_two_meals_on_one_day_extend_by_one(self) -> None:
        # Two meals today and one yesterday: today is one day, not two.
        entries = [_meal(TODAY), _meal(TODAY), _meal(TODAY - timedelta(days=1))]
        assert meal_streak(entries, TODAY) == 2

    def test_empty_today_stays_pending(self) -> None:
        # Meals each of the prior 5 elapsed days, none today: 5, not 6.
        entries = [_meal(TODAY - timedelta(days=back)) for back in range(1, 6)]
        assert meal_streak(entries, TODAY) == 5

    def test_elapsed_empty_day_breaks(self) -> None:
        # Meals today and two days ago; the elapsed day in between has none -> 1.
        entries = [_meal(TODAY), _meal(TODAY - timedelta(days=2))]
        assert meal_streak(entries, TODAY) == 1


class TestStreakState:
    def test_empty_histories_yield_zero_state(self) -> None:
        assert streak_state([], [], [], TODAY) == StreakState(0, 0, 0)

    def test_combines_all_three_streaks(self) -> None:
        weights = [_weight(_week_monday(back)) for back in range(3)]
        exercise = [_exercise(_week_monday(0)) for _ in range(3)]
        meals = [_meal(TODAY), _meal(TODAY - timedelta(days=1))]
        state = streak_state(exercise, meals, weights, TODAY)
        assert state == StreakState(weight_weeks=3, exercise_weeks=1, meal_days=2)
