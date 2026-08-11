"""Achievements engine derivation tests (R2 · S1): the spec scenarios for
the pure engine — catalogue/empty state, quest thresholds with ``streak_alive``
exclusion, Consistency any-window, Comeback runs, Personal Best sums (the
gather/API layer and cross-user isolation land in S2).
"""

import pytest

import achievements
from constants import ACHIEVEMENTS
from models import (
    AchievementFacts,
    AchievementQuestFact,
    ExerciseDayFacts,
    MomentumDayFacts,
)


def _quest(day: str, key: str, domain: str = "exercise") -> AchievementQuestFact:
    return AchievementQuestFact(date=day, quest_key=key, domain=domain)


def _day(day: str, *, assigned: int = 0, done: int = 0, log_rows: int = 0) -> MomentumDayFacts:
    return MomentumDayFacts(date=day, assigned_quests=assigned, done_quests=done, log_rows=log_rows)


def _exercise(day: str, minutes: int) -> ExerciseDayFacts:
    return ExerciseDayFacts(date=day, duration_min=minutes)


def _good(day: str) -> MomentumDayFacts:  # assigned quest done → successful
    return _day(day, assigned=1, done=1)


def _spark(day: str) -> MomentumDayFacts:  # one action, assignment open → not successful
    return _day(day, assigned=1, log_rows=1)


def _inactive(day: str) -> MomentumDayFacts:  # assigned quest, zero actions
    return _day(day, assigned=1)


def _states(facts: AchievementFacts) -> dict[str, achievements.AchievementState]:
    return {state.key: state for state in achievements.states(facts, ACHIEVEMENTS)}


class TestCatalogueAndEmptyState:
    def test_catalogue_order_and_empty_state(self) -> None:
        # The catalogue preserves the six-key order; with no qualifying
        # history every state appears locked in that order with null dates.
        assert ACHIEVEMENTS == (
            ("getting_started", "Getting Started"),
            ("moving_forward", "Moving Forward"),
            ("consistency", "Consistency"),
            ("comeback", "Comeback"),
            ("explorer", "Explorer"),
            ("personal_best", "Personal Best"),
        )
        states = achievements.states(AchievementFacts(), ACHIEVEMENTS)
        assert [s.key for s in states] == [key for key, _ in ACHIEVEMENTS]
        assert [s.title for s in states] == [title for _, title in ACHIEVEMENTS]
        assert all(not s.earned for s in states)
        assert all(s.unlocked_at is None for s in states)


class TestQuestAchievements:
    def test_threshold_dates_across_all_three(self) -> None:
        # First quest 07-01, tenth exercise_10 on 07-14, fifth first-seen domain (wellbeing) on 07-05.
        facts = AchievementFacts(
            done_quests=[
                _quest("2026-07-01", "exercise_10"),
                _quest("2026-07-02", "log_meal", domain="nutrition"),
                _quest("2026-07-03", "streak_alive", domain="movement"),
                _quest("2026-07-04", "habit_checkin", domain="routine"),
                _quest("2026-07-05", "mood_checkin", domain="wellbeing"),
                *[_quest(f"2026-07-{d:02d}", "exercise_10") for d in range(6, 15)],
            ]
        )
        states = _states(facts)
        assert states["getting_started"].earned is True
        assert states["getting_started"].unlocked_at == "2026-07-01"
        assert states["moving_forward"].unlocked_at == "2026-07-14"
        assert states["explorer"].unlocked_at == "2026-07-05"

    @pytest.mark.parametrize(
        ("done_quests", "locked"),
        [
            # nine exercise_10 + five streak_alive → Moving Forward stays locked
            (
                [*[_quest(f"2026-07-{d:02d}", "exercise_10") for d in range(1, 10)],
                 *[_quest(f"2026-07-{d:02d}", "streak_alive", domain="movement") for d in range(10, 15)]],
                "moving_forward",
            ),
            # four distinct domains → Explorer stays locked
            (
                [_quest("2026-07-01", "exercise_10"),
                 _quest("2026-07-02", "log_meal", domain="nutrition"),
                 _quest("2026-07-03", "streak_alive", domain="movement"),
                 _quest("2026-07-04", "habit_checkin", domain="routine")],
                "explorer",
            ),
        ],
    )
    def test_stays_locked_below_threshold(
        self, done_quests: list[AchievementQuestFact], locked: str
    ) -> None:
        state = _states(AchievementFacts(done_quests=done_quests))[locked]
        assert state.earned is False
        assert state.unlocked_at is None


class TestConsistency:
    def test_any_window_qualification_earliest_span(self) -> None:
        # 07-03/07-06 missing (neutral): first qualifying window 07-01..07-07,
        # fifth success 07-07; the 06-28..07-04 window holds four, so it loses.
        facts = AchievementFacts(
            momentum_days=[
                _good(day)
                for day in ("2026-06-28", "2026-07-01", "2026-07-02", "2026-07-04", "2026-07-05", "2026-07-07")
            ]
        )
        states = _states(facts)
        assert states["consistency"].earned is True
        assert states["consistency"].unlocked_at == "2026-07-07"

    @pytest.mark.parametrize(
        "days",
        [
            # four Good + one Spark + two inactive neutral days → locked
            [_good("2026-07-01"), _good("2026-07-02"), _good("2026-07-03"), _good("2026-07-04"),
             _spark("2026-07-05"), _inactive("2026-07-06"), _inactive("2026-07-07")],
            # five Good days over only five dates: no seven-date window yet
            [_good(f"2026-07-{d:02d}") for d in range(1, 6)],
        ],
    )
    def test_stays_locked(self, days: list[MomentumDayFacts]) -> None:
        assert _states(AchievementFacts(momentum_days=days))["consistency"].earned is False


class TestComeback:
    @pytest.mark.parametrize(
        ("days", "expected"),
        [
            # Spark return immediately after three inactive days.
            ([_inactive("2026-07-01"), _inactive("2026-07-02"), _inactive("2026-07-03"), _spark("2026-07-04")], "2026-07-04"),
            # Skipped-only days stay assigned with zero actions → inactive run.
            ([_day("2026-07-01", assigned=1), _day("2026-07-02", assigned=1), _day("2026-07-03", assigned=1), _spark("2026-07-04")], "2026-07-04"),
        ],
    )
    def test_earns_on_earliest_return_date(self, days: list[MomentumDayFacts], expected: str) -> None:
        states = _states(AchievementFacts(momentum_days=days))
        assert states["comeback"].earned is True
        assert states["comeback"].unlocked_at == expected

    @pytest.mark.parametrize(
        "days",
        [
            # A replaced-only date (no current assignments) breaks the run.
            [_inactive("2026-07-01"), _inactive("2026-07-02"), _day("2026-07-03"), _spark("2026-07-04")],
            # A missing date between inactive days breaks the run.
            [_inactive("2026-07-01"), _inactive("2026-07-03"), _inactive("2026-07-04"), _spark("2026-07-05")],
            # Fewer than three inactive days before the return.
            [_inactive("2026-07-01"), _inactive("2026-07-02"), _spark("2026-07-03")],
        ],
    )
    def test_stays_locked_when_run_is_broken(self, days: list[MomentumDayFacts]) -> None:
        state = _states(AchievementFacts(momentum_days=days))["comeback"]
        assert state.earned is False
        assert state.unlocked_at is None


class TestPersonalBest:
    @pytest.mark.parametrize(
        ("days", "expected"),
        [
            # First positive daily sum qualifies (zero for empty pre-history).
            ([_exercise("2026-07-01", 30)], "2026-07-01"),
            # The date stays on the EARLIEST qualifying day, never a later record.
            ([_exercise("2026-07-01", 30), _exercise("2026-07-02", 45), _exercise("2026-07-03", 20)], "2026-07-01"),
            # Zero-sum earlier days never qualify.
            ([_exercise("2026-07-01", 0), _exercise("2026-07-02", 30)], "2026-07-02"),
        ],
    )
    def test_earns_on_earliest_qualifying_day(self, days: list[ExerciseDayFacts], expected: str) -> None:
        states = _states(AchievementFacts(exercise_days=days))
        assert states["personal_best"].earned is True
        assert states["personal_best"].unlocked_at == expected

    @pytest.mark.parametrize(
        "days",
        [
            [],  # no evidence at all
            [_exercise("2026-07-01", 0)],  # only zero-sum evidence remains
        ],
    )
    def test_relocks_when_no_positive_evidence_remains(self, days: list[ExerciseDayFacts]) -> None:
        state = _states(AchievementFacts(exercise_days=days))["personal_best"]
        assert state.earned is False
        assert state.unlocked_at is None
