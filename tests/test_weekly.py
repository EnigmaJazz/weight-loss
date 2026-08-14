"""Pure weekly-objectives engine tests (PR 2 · S2).

Pins the weekly-objectives spec (R5/R7) at the pure layer: Mon–Sun week
identity with ISO-year rollover, the exact 10/3 targets, met-ness from week
facts, momentum-semantics good-day counting (Spark and unclassified days
excluded), and the forward-only per-user activation exemption rule.
"""

from datetime import date, timedelta

from models import MomentumDayFacts
import weekly

MONDAY = date(2026, 8, 3)
WEDNESDAY = date(2026, 8, 5)
SUNDAY = date(2026, 8, 9)


def _facts(day: date, assigned: int = 0, done: int = 0, log_rows: int = 0) -> MomentumDayFacts:
    """One MomentumDayFacts row for ``day`` with the given counts."""
    return MomentumDayFacts(
        date=day.isoformat(),
        assigned_quests=assigned,
        done_quests=done,
        log_rows=log_rows,
    )


class TestWeekStart:
    def test_every_weekday_maps_to_its_monday(self) -> None:
        # Mon–Sun weeks: each of the seven weekdays resolves to the same Monday.
        for offset in range(7):
            assert weekly.week_start(MONDAY + timedelta(days=offset)) == MONDAY

    def test_explicit_monday_tuesday_sunday(self) -> None:
        assert weekly.week_start(WEDNESDAY) == MONDAY
        assert weekly.week_start(SUNDAY) == MONDAY
        assert weekly.week_start(MONDAY) == MONDAY

    def test_iso_year_rollover(self) -> None:
        # New Year's Day 2027 (Friday) sits in the Mon 2026-12-28 week, and
        # 2021-01-01 (Friday) in the Mon 2020-12-28 week (ISO week 53 of 2020).
        assert weekly.week_start(date(2027, 1, 1)) == date(2026, 12, 28)
        assert weekly.week_start(date(2026, 12, 31)) == date(2026, 12, 28)
        assert weekly.week_start(date(2021, 1, 1)) == date(2020, 12, 28)
        assert weekly.week_start(date(2020, 12, 28)) == date(2020, 12, 28)


class TestGoalTargets:
    def test_exact_thresholds_are_met(self) -> None:
        # R5 scenario: 10 done quests and 3 Good/Great days meet both objectives.
        assert weekly.goal_met("quests", 10) is True
        assert weekly.goal_met("good_days", 3) is True

    def test_below_threshold_is_unmet(self) -> None:
        assert weekly.goal_met("quests", 9) is False
        assert weekly.goal_met("good_days", 2) is False
        assert weekly.goal_met("quests", 0) is False
        assert weekly.goal_met("good_days", 0) is False

    def test_targets_are_ten_and_three(self) -> None:
        assert weekly.WEEK_TARGETS == {"quests": 10, "good_days": 3}

    def test_award_is_forty_xp(self) -> None:
        assert weekly.WEEK_AWARD_XP == 40

    def test_goal_state_shape(self) -> None:
        met = weekly.goal_state("quests", 10, awarded=True)
        assert (met.goal, met.current, met.target, met.met, met.awarded) == (
            "quests",
            10,
            10,
            True,
            True,
        )
        unmet = weekly.goal_state("good_days", 2, awarded=False)
        assert unmet.met is False and unmet.awarded is False
        assert unmet.target == 3


class TestGoodDayCounting:
    def test_spark_and_unclassified_days_excluded(self) -> None:
        # R5 scenario: a one-action Spark day and a day with no assigned quests
        # never advance the good-days objective (momentum is_successful reuse).
        days = [
            _facts(MONDAY, assigned=1, done=1),  # Great Day (successful)
            _facts(MONDAY + timedelta(days=1), assigned=2, done=1),  # Spark
            _facts(MONDAY + timedelta(days=2)),  # unclassified (no assignment)
            _facts(MONDAY + timedelta(days=3), assigned=2, done=1, log_rows=1),  # Good
        ]
        assert weekly.good_day_count(days, MONDAY) == 2

    def test_good_and_great_days_both_count(self) -> None:
        days = [
            _facts(MONDAY, assigned=2, done=1, log_rows=1),  # Good Day
            _facts(MONDAY + timedelta(days=1), assigned=2, done=2),  # Great Day
        ]
        assert weekly.good_day_count(days, MONDAY) == 2

    def test_empty_week_counts_zero(self) -> None:
        assert weekly.good_day_count([], MONDAY) == 0

    def test_days_outside_the_week_are_ignored(self) -> None:
        days = [
            _facts(MONDAY, assigned=1, done=1),  # inside: Great
            _facts(MONDAY - timedelta(days=1), assigned=2, done=2),  # outside
            _facts(MONDAY + timedelta(days=7), assigned=2, done=2),  # outside
        ]
        assert weekly.good_day_count(days, MONDAY) == 1


class TestActivationExemption:
    def test_mid_week_activation_exempts_partial_week(self) -> None:
        # R7 scenario: activation on Wednesday exempts the current and earlier
        # weeks; the following Monday starts the first counted week.
        assert weekly.is_counted_week(MONDAY, WEDNESDAY) is False
        assert weekly.is_counted_week(MONDAY + timedelta(days=7), WEDNESDAY) is True

    def test_monday_activation_counts_the_current_week(self) -> None:
        # Activation exactly at the Monday boundary is not "after a Monday
        # begins": the week is full and counts from its own start.
        assert weekly.is_counted_week(MONDAY, MONDAY) is True

    def test_first_counted_week_is_next_monday(self) -> None:
        assert weekly.first_counted_week(WEDNESDAY) == MONDAY + timedelta(days=7)
        assert weekly.first_counted_week(MONDAY) == MONDAY

    def test_pre_activation_weeks_never_count(self) -> None:
        activation = WEDNESDAY
        assert weekly.is_counted_week(MONDAY - timedelta(days=7), activation) is False
        assert weekly.is_counted_week(MONDAY, activation) is False
