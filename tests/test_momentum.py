"""Momentum derivation tests (PR 4 · S2b).

Covers the momentum spec scenarios: the exact tier boundaries (zero actions
with assignments → none, one action → Spark, two → Good Day; Great Day when
every current assignment is done with at least one action, taking precedence
over lower tiers; a skipped quest blocks Great Day), the successful-day
predicate, the inclusive trailing 21-day window (including today, day 22
excluded), and no-quest days resolving to none regardless of logs. A
database-layer group verifies the bulk per-date facts query plus per-user
isolation; the API surface lives in test_api.py.
"""

from datetime import date, timedelta

import momentum
from database import Database
from models import MomentumDayFacts, MomentumState
from tests.conftest import make_user
import quests

# A fixed "today" so window math is deterministic and relative.
TODAY = date(2026, 8, 9)
START = (TODAY - timedelta(days=20)).isoformat()  # window start (today - 20)


def _facts(
    day: date,
    *,
    assigned: int = 0,
    done: int = 0,
    log_rows: int = 0,
) -> MomentumDayFacts:
    """A MomentumDayFacts with the per-date counts the classifier consumes."""
    return MomentumDayFacts(
        date=day.isoformat(),
        assigned_quests=assigned,
        done_quests=done,
        log_rows=log_rows,
    )


def _seed_done(db: Database, user_id: int, day: date, keys: list[str]) -> None:
    """Insert one quest per key for ``day`` and mark each done."""
    rows = db.insert_quests(
        user_id, day.isoformat(), [quests.draft_for_key(key, day) for key in keys]
    )
    for row in rows:
        db.update_quest_status(user_id, row.id, "done")


class TestTierMatrix:
    def test_zero_actions_with_assignments_is_none(self) -> None:
        # Three open quests, no log rows: no actions → none (spec boundaries).
        assert momentum.classify_day(_facts(TODAY, assigned=3)) == "none"

    def test_one_action_is_spark(self) -> None:
        assert momentum.classify_day(_facts(TODAY, assigned=3, log_rows=1)) == "Spark"

    def test_two_actions_is_good_day(self) -> None:
        # Two meal rows with open quests → Good Day.
        assert (
            momentum.classify_day(_facts(TODAY, assigned=3, log_rows=2))
            == "Good Day"
        )

    def test_done_quest_counts_as_action(self) -> None:
        # Spec "count quests and logs": one done quest + one meal row = 2.
        assert momentum.action_count(_facts(TODAY, done=1, log_rows=1)) == 2
        assert (
            momentum.classify_day(_facts(TODAY, assigned=2, done=1, log_rows=1))
            == "Good Day"
        )

    def test_great_day_when_all_current_done(self) -> None:
        # Every assigned quest done → Great Day, with or without extra logs.
        assert (
            momentum.classify_day(_facts(TODAY, assigned=3, done=3))
            == "Great Day"
        )
        assert (
            momentum.classify_day(_facts(TODAY, assigned=1, done=1, log_rows=1))
            == "Great Day"
        )

    def test_great_day_precedes_good_day(self) -> None:
        # All done PLUS extra log rows still resolves to Great Day, never Good.
        assert (
            momentum.classify_day(_facts(TODAY, assigned=2, done=2, log_rows=2))
            == "Great Day"
        )

    def test_skipped_quest_blocks_great_day(self) -> None:
        # A skipped quest is assigned but not done → not Great; with two
        # actions (done quest + log row) the day is Good Day (spec skipped
        # edge), and with one action it stays Spark.
        assert (
            momentum.classify_day(_facts(TODAY, assigned=3, done=1, log_rows=1))
            == "Good Day"
        )
        assert momentum.classify_day(_facts(TODAY, assigned=2, done=1)) == "Spark"

    def test_no_assignments_none_regardless_of_logs(self) -> None:
        # Spec: a date with no assigned quests is none even with log rows.
        assert momentum.classify_day(_facts(TODAY, log_rows=5)) == "none"

    def test_successful_predicate(self) -> None:
        # Good Day and Great Day are successful; Spark and none are not.
        assert momentum.is_successful("Good Day") is True
        assert momentum.is_successful("Great Day") is True
        assert momentum.is_successful("Spark") is False
        assert momentum.is_successful("none") is False


class TestTrailingWindow:
    def test_window_dates_math(self) -> None:
        # The trailing window is 21 local calendar dates ending today
        # (inclusive), ascending.
        days = momentum.window_dates(TODAY)
        assert len(days) == 21
        assert days[0] == TODAY - timedelta(days=20)
        assert days[-1] == TODAY
        assert days == sorted(days)

    def test_inclusive_21_days(self) -> None:
        # Spec: 18 of the 21 window dates are Good/Great → successful_days 18,
        # window_days 21. Three dates (offsets 0/7/14) get one action → Spark.
        facts = [
            _facts(TODAY - timedelta(days=offset), assigned=3, log_rows=2)
            if offset % 7
            else _facts(TODAY - timedelta(days=offset), assigned=3, log_rows=1)
            for offset in range(21)
        ]
        state = momentum.momentum_state(facts, TODAY)
        assert state.window_days == 21
        assert state.successful_days == 18
        # Offset 0 is today, one of the three Spark days (1 action).
        assert state.today_tier == "Spark"
        assert state.is_successful_today is False

    def test_day_22_excluded(self) -> None:
        # Spec: a successful day at today−21 falls outside the window and must
        # not contribute; only today's Spark counts in-window.
        facts = [
            _facts(TODAY - timedelta(days=21), assigned=3, done=3),  # Great, out
            _facts(TODAY, assigned=3, log_rows=1),  # Spark today
        ]
        state = momentum.momentum_state(facts, TODAY)
        assert state.window_days == 21
        assert state.successful_days == 0
        assert state.today_tier == "Spark"
        assert state.is_successful_today is False

    def test_today_contributes_to_window(self) -> None:
        # The window ends today: today's Good Day counts toward the total.
        state = momentum.momentum_state([_facts(TODAY, assigned=3, log_rows=2)], TODAY)
        assert state.today_tier == "Good Day"
        assert state.is_successful_today is True
        assert state.successful_days == 1
        assert state.window_days == 21


class TestNoQuests:
    def test_no_facts_anywhere_is_none(self) -> None:
        # A user with no quest rows and no log rows: today none, window 21.
        state = momentum.momentum_state([], TODAY)
        assert state.today_tier == "none"
        assert state.is_successful_today is False
        assert state.window_days == 21
        assert state.successful_days == 0

    def test_logs_without_quest_rows_are_none(self) -> None:
        # A weight entry alone (no quest rows that date) is still none.
        state = momentum.momentum_state([_facts(TODAY, log_rows=1)], TODAY)
        assert state.today_tier == "none"
        assert state.is_successful_today is False


# ---- database-layer facts (conftest tmp_path DB) -------------------------


class TestMomentumFactsPersistence:
    def test_actions_count_quests_and_logs(self, tmp_path) -> None:
        """Spec: one done quest + one meal row today → the facts carry
        done_quests 1 and log_rows 1, so the action count is 2. With the only
        assignment done and an action present the tier is Great Day."""
        db = Database(str(tmp_path / "momentum.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-mom")
            _seed_done(db, alice.id, TODAY, ["log_meal"])
            db.insert_meal(alice.id, TODAY.isoformat(), 600.0)
            facts = db.momentum_facts(alice.id, START, TODAY.isoformat())
            today = next(f for f in facts if f.date == TODAY.isoformat())
            assert today.done_quests == 1
            assert today.log_rows == 1
            assert momentum.action_count(today) == 2
            assert momentum.classify_day(today) == "Great Day"
        finally:
            db.close()

    def test_replaced_not_current_and_skipped_blocks_great(self, tmp_path) -> None:
        """Replaced rows are not current assignments; a skipped quest keeps the
        day below Great. Done+skipped+open → assigned 3, done 1 → Spark.
        Note insert_quests returns every row for the day, so the replacement
        row is picked by its quest_key."""
        db = Database(str(tmp_path / "momentum.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-replace")
            rows = db.insert_quests(
                alice.id,
                TODAY.isoformat(),
                [
                    quests.draft_for_key("log_meal", TODAY),
                    quests.draft_for_key("exercise_10", TODAY),
                    quests.draft_for_key("mood_checkin", TODAY),
                ],
            )
            db.update_quest_status(alice.id, rows[0].id, "done")
            db.update_quest_status(alice.id, rows[1].id, "skipped")
            replaced = next(
                q
                for q in db.insert_quests(
                    alice.id,
                    TODAY.isoformat(),
                    [quests.draft_for_key("streak_alive", TODAY)],
                )
                if q.quest_key == "streak_alive"
            )
            db.update_quest_status(alice.id, replaced.id, "replaced")
            facts = db.momentum_facts(alice.id, START, TODAY.isoformat())
            today = next(f for f in facts if f.date == TODAY.isoformat())
            assert today.assigned_quests == 3  # replaced row excluded
            assert today.done_quests == 1
            assert momentum.classify_day(today) == "Spark"
        finally:
            db.close()

    def test_per_user_isolation(self, tmp_path) -> None:
        """Spec: another user's actions never affect this user's facts."""
        db = Database(str(tmp_path / "momentum.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-iso")
            bob = make_user(db, "bob-iso")
            _seed_done(db, alice.id, TODAY, ["log_meal"])
            _seed_done(db, bob.id, TODAY, ["exercise_10", "log_weight", "streak_alive"])
            db.insert_meal(bob.id, TODAY.isoformat(), 500.0)
            facts = db.momentum_facts(alice.id, START, TODAY.isoformat())
            assert len(facts) == 1  # only alice's date surfaces
            assert facts[0].date == TODAY.isoformat()
            assert facts[0].done_quests == 1
            assert facts[0].log_rows == 0
        finally:
            db.close()

    def test_no_rows_returns_empty(self, tmp_path) -> None:
        """A user with no quest/log rows in the window gets no facts; the pure
        layer resolves every window date to none."""
        db = Database(str(tmp_path / "momentum.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-empty")
            assert db.momentum_facts(alice.id, START, TODAY.isoformat()) == []
            state = momentum.momentum_state(
                db.momentum_facts(alice.id, START, TODAY.isoformat()), TODAY
            )
            assert state.today_tier == "none"
            assert state.successful_days == 0
            assert state.window_days == 21
        finally:
            db.close()
