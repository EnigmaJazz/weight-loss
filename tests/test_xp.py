"""XP derivation tests (PR 3 · S2a).

Covers the xp-progression spec scenarios: the exact level curve (0/99/100/249/
250/449/450 boundaries), progress within a level, title band boundaries
(1/4/5/9/10/19/20/29/30), the derived SUM of done quests only (skipped and
replaced contribute zero), per-user isolation, and bounded recent completions.
"""

from datetime import date

from constants import (
    LEVEL_TITLES,
    LEVEL_XP_PER_LEVEL,
    LEVEL_XP_STEP,
    QUEST_POOL,
)
from database import Database
from models import AppSettings
import quests
import xp
from tests.conftest import make_user

MONDAY = date(2026, 8, 3)
WEDNESDAY = date(2026, 8, 5)
SUNDAY = date(2026, 8, 9)

# Four past quest-days for recent-completion ordering tests (all Mondays).
RECENT_DAYS = (date(2026, 7, 6), date(2026, 7, 13), date(2026, 7, 20), date(2026, 7, 27))


def _pool_by_key() -> dict[str, tuple[str, str, str, str, int, str]]:
    """Pool entries keyed by quest key: (key, domain, title, desc, xp, size)."""
    return {entry[0]: entry for entry in QUEST_POOL}


class TestLevelConstants:
    def test_curve_constants(self) -> None:
        # Advancing from level n costs LEVEL_XP_PER_LEVEL + (n-1)*LEVEL_XP_STEP.
        assert LEVEL_XP_PER_LEVEL == 100
        assert LEVEL_XP_STEP == 50

    def test_title_bands_exact(self) -> None:
        # (min_level, title) ascending — normative per the xp-progression spec:
        # 1-4 Sprout, 5-9 Explorer, 10-19 Adventurer, 20-29 Champion, 30+ Legend.
        assert LEVEL_TITLES == (
            (1, "Sprout"),
            (5, "Explorer"),
            (10, "Adventurer"),
            (20, "Champion"),
            (30, "Legend"),
        )


class TestLevelCurve:
    def test_level_one_starts_at_zero(self) -> None:
        assert xp.threshold_for_level(1) == 0
        assert xp.level_from_xp(0) == 1

    def test_threshold_vectors(self) -> None:
        # T(L) = 25*(L-1)*(L+2): 0, 100, 250, 450, 700...
        assert [xp.threshold_for_level(l) for l in (1, 2, 3, 4, 5)] == [
            0,
            100,
            250,
            450,
            700,
        ]
        # Level from XP: greatest L whose threshold is not above the total.
        assert xp.level_from_xp(99) == 1
        assert xp.level_from_xp(100) == 2
        assert xp.level_from_xp(249) == 2
        assert xp.level_from_xp(250) == 3
        assert xp.level_from_xp(449) == 3
        assert xp.level_from_xp(450) == 4

    def test_advance_cost_matches_constants(self) -> None:
        # The step between consecutive thresholds is the stated advance cost,
        # at low, mid, and high levels (no hardcoded 25 hidden in the math).
        for level in (1, 2, 3, 10, 50):
            assert (
                xp.threshold_for_level(level + 1) - xp.threshold_for_level(level)
                == LEVEL_XP_PER_LEVEL + (level - 1) * LEVEL_XP_STEP
            )

    def test_large_totals_are_exact(self) -> None:
        # Integer-exact far above the spec vectors (no float drift at exact
        # boundaries): T(100) = 25*99*102 = 252450.
        assert xp.level_from_xp(699) == 4
        assert xp.level_from_xp(700) == 5
        assert xp.level_from_xp(252449) == 99
        assert xp.level_from_xp(252450) == 100


class TestProgressVectors:
    def test_progress_within_level(self) -> None:
        # Between T(L) and T(L+1): xp_into_next = total - T(L),
        # next_level_at = T(L+1) (spec scenario).
        assert xp.level_progress(80) == (80, 100)  # level 1, 80 into 100
        assert xp.level_progress(120) == (20, 250)  # level 2, 20 into 250
        assert xp.level_progress(0) == (0, 100)  # fresh user
        assert xp.level_progress(100) == (0, 250)  # exactly at a boundary
        assert xp.level_progress(250) == (0, 450)
        assert xp.level_progress(450) == (0, 700)


class TestTitleBands:
    def test_title_band_boundaries(self) -> None:
        # Spec scenario: levels 4, 5, 29, 30 → Sprout, Explorer, Champion,
        # Legend — plus every band's upper edge and 30+ Legend.
        assert xp.title_for_level(1) == "Sprout"
        assert xp.title_for_level(4) == "Sprout"
        assert xp.title_for_level(5) == "Explorer"
        assert xp.title_for_level(9) == "Explorer"
        assert xp.title_for_level(10) == "Adventurer"
        assert xp.title_for_level(19) == "Adventurer"
        assert xp.title_for_level(20) == "Champion"
        assert xp.title_for_level(29) == "Champion"
        assert xp.title_for_level(30) == "Legend"
        assert xp.title_for_level(100) == "Legend"


# ---- database-layer persistence (conftest tmp_path DB) ----------------


def _mark_done(db: Database, user_id: int, day: date, keys: list[str]) -> None:
    """Insert one quest per key for ``day`` and mark each done."""
    rows = db.insert_quests(
        user_id, day.isoformat(), [quests.draft_for_key(key, day) for key in keys]
    )
    for row in rows:
        db.update_quest_status(user_id, row.id, "done")


class TestXpPersistence:
    def test_total_xp_sums_only_done(self, tmp_path) -> None:
        """Spec scenario: done quests worth 20 and 40 plus skipped and replaced
        quests worth 40 → total XP is 60; open quests contribute nothing."""
        db = Database(str(tmp_path / "xp.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-xp")
            bob = make_user(db, "bob-xp")
            _mark_done(db, alice.id, MONDAY, ["log_meal", "exercise_10"])  # 20 + 40
            skipped = db.insert_quests(
                alice.id, WEDNESDAY.isoformat(), [quests.draft_for_key("log_weight", WEDNESDAY)]
            )
            db.update_quest_status(alice.id, skipped[0].id, "skipped")
            replaced = db.insert_quests(
                alice.id, SUNDAY.isoformat(), [quests.draft_for_key("streak_alive", SUNDAY)]
            )
            db.update_quest_status(alice.id, replaced[0].id, "replaced")
            # An open quest (no status transition) also contributes zero.
            db.insert_quests(
                alice.id, SUNDAY.isoformat(), [quests.draft_for_key("mood_checkin", SUNDAY)]
            )
            assert db.total_xp_for_user(alice.id) == 60
            # Per-user isolation: bob's done quests never contribute to alice.
            _mark_done(db, bob.id, MONDAY, ["exercise_10"])
            assert db.total_xp_for_user(bob.id) == 40
            assert db.total_xp_for_user(alice.id) == 60
            # A user with no quests has zero XP, never None.
            assert db.total_xp_for_user(make_user(db, "empty-xp").id) == 0
        finally:
            db.close()

    def test_recent_done_quests_bounded_and_newest_first(self, tmp_path) -> None:
        """Recent completions: only done quests, newest date first, capped by
        limit — the GET /api/xp surface. Quests complete on their own date, so
        date order is completion order."""
        db = Database(str(tmp_path / "xp.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-recent")
            bob = make_user(db, "bob-recent")
            for day in RECENT_DAYS:  # 4 days x 3 quests = 12 done (> the bound)
                rows = db.insert_quests(
                    alice.id,
                    day.isoformat(),
                    quests.generate_quests(alice.id, day, AppSettings(reminder_weekday=0)),
                )
                for row in rows:
                    db.update_quest_status(alice.id, row.id, "done")
            recent = db.list_recent_done_quests(alice.id, limit=10)
            assert len(recent) == 10  # bounded
            assert all(row.status == "done" for row in recent)
            # Newest date first: the 2026-07-27 batch leads, 2026-07-06 trails.
            assert [row.date for row in recent] == (
                ["2026-07-27"] * 3
                + ["2026-07-20"] * 3
                + ["2026-07-13"] * 3
                + ["2026-07-06"]
            )
            # Bob sees none of alice's completions.
            assert db.list_recent_done_quests(bob.id, limit=10) == []
            # The bound is honored from the DB layer directly.
            assert len(db.list_recent_done_quests(alice.id, limit=5)) == 5
        finally:
            db.close()
