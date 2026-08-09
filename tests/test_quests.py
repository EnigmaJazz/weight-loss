"""Quest engine + quest persistence tests (PR 1 · S1a).

Covers the daily-quests spec scenarios: deterministic generation (weigh-in vs
other weekdays), seed stability, no duplicate keys per day, lifecycle
transitions (idempotent done, terminal skip/replace), the one-replacement-per-
day cap with key exclusions, read-detected completion from entry facts, and
persistence through the database layer (conftest tmp_path DB).
"""

from datetime import date

from constants import QUEST_POOL
from database import Database
from models import AppSettings, Quest, QuestDetectionFacts
import quests
from tests.conftest import make_user

# Fixed weekdays: Monday=0, Wednesday=2, Sunday=6 (datetime.weekday()).
MONDAY = date(2026, 8, 3)
WEDNESDAY = date(2026, 8, 5)
SUNDAY = date(2026, 8, 9)


def _pool_by_key() -> dict[str, tuple[str, str, str, str, int, str]]:
    """Pool entries keyed by quest key: (key, domain, title, desc, xp, size)."""
    return {entry[0]: entry for entry in QUEST_POOL}


def _draft(
    key: str = "log_meal",
    status: str = "open",
    completed_at: str | None = None,
    source: str = "rules",
) -> Quest:
    """A Quest instance with catalogue fields filled from QUEST_POOL."""
    _, domain, title, description, xp_value, difficulty = _pool_by_key()[key]
    return Quest(
        id=0,
        date=WEDNESDAY.isoformat(),
        quest_key=key,
        domain=domain,
        title=title,
        description=description,
        xp_value=xp_value,
        status=status,
        difficulty=difficulty,
        source=source,
        completed_at=completed_at,
        created_at="",
    )


class TestQuestPool:
    def test_catalogue_order_and_values(self) -> None:
        by_key = _pool_by_key()
        # Catalogue order: rotation pool first, then mandatory + weekly keys.
        assert [entry[0] for entry in QUEST_POOL][:4] == [
            "exercise_10",
            "log_meal",
            "streak_alive",
            "habit_checkin",
        ]
        assert set(by_key) == {
            "log_weight",
            "mood_checkin",
            "exercise_10",
            "log_meal",
            "streak_alive",
            "habit_checkin",
        }
        # Normative XP values (spec table: small/20, normal/40).
        assert by_key["log_weight"][4] == 20
        assert by_key["mood_checkin"][4] == 20
        assert by_key["exercise_10"][4] == 40
        assert by_key["log_meal"][4] == 20
        assert by_key["streak_alive"][4] == 20
        assert by_key["habit_checkin"][4] == 20
        # Normative domains and sizes.
        assert (by_key["log_weight"][1], by_key["log_weight"][5]) == ("weight", "small")
        assert (by_key["mood_checkin"][1], by_key["mood_checkin"][5]) == (
            "wellbeing",
            "small",
        )
        assert (by_key["exercise_10"][1], by_key["exercise_10"][5]) == (
            "exercise",
            "normal",
        )
        assert (by_key["log_meal"][1], by_key["log_meal"][5]) == ("nutrition", "small")
        assert (by_key["streak_alive"][1], by_key["streak_alive"][5]) == (
            "movement",
            "small",
        )
        assert (by_key["habit_checkin"][1], by_key["habit_checkin"][5]) == (
            "routine",
            "small",
        )


class TestGenerationMatrix:
    def test_weigh_in_day_composition(self) -> None:
        # reminder_weekday=0 (Monday) → log_weight + mood_checkin + 1 rotating.
        quests_for_day = quests.generate_quests(1, MONDAY, AppSettings(reminder_weekday=0))
        keys = {q.quest_key for q in quests_for_day}
        assert len(quests_for_day) == 3
        assert len(keys) == 3  # never duplicate keys within a day
        assert "log_weight" in keys
        assert "mood_checkin" in keys
        rotating = keys - {"log_weight", "mood_checkin"}
        assert len(rotating) == 1
        assert rotating <= set(quests.ROTATION_POOL)

    def test_other_day_composition(self) -> None:
        # reminder_weekday=0 → Wednesday is NOT a weigh-in day.
        quests_for_day = quests.generate_quests(1, WEDNESDAY, AppSettings(reminder_weekday=0))
        keys = {q.quest_key for q in quests_for_day}
        assert len(quests_for_day) == 3
        assert len(keys) == 3
        assert "mood_checkin" in keys
        assert "log_weight" not in keys
        rotating = keys - {"mood_checkin"}
        assert len(rotating) == 2
        assert rotating <= set(quests.ROTATION_POOL)

    def test_drafts_carry_catalogue_fields(self) -> None:
        by_key = _pool_by_key()
        quests_for_day = quests.generate_quests(1, WEDNESDAY, AppSettings(reminder_weekday=0))
        for q in quests_for_day:
            entry = by_key[q.quest_key]
            assert q.status == "open"
            assert q.source == "rules"
            assert q.difficulty == entry[5]
            assert q.xp_value == entry[4]
            assert q.domain == entry[1]
            assert q.date == WEDNESDAY.isoformat()
            assert q.completed_at is None
        # XP follows the normative table: 20 except exercise_10 → 40.
        xp_by_key = {q.quest_key: q.xp_value for q in quests_for_day}
        for key, xp in xp_by_key.items():
            assert xp == (40 if key == "exercise_10" else 20)

    def test_never_duplicates_across_users_and_dates(self) -> None:
        for user_id in (1, 2, 3, 7, 42):
            for day in (MONDAY, WEDNESDAY, SUNDAY):
                keys = [q.quest_key for q in quests.generate_quests(
                    user_id, day, AppSettings(reminder_weekday=0)
                )]
                assert len(keys) == 3
                assert len(set(keys)) == 3


class TestWeekdayRule:
    def test_reminder_weekday_mapping(self) -> None:
        assert quests.is_weigh_in_day(MONDAY, AppSettings(reminder_weekday=0)) is True
        assert quests.is_weigh_in_day(WEDNESDAY, AppSettings(reminder_weekday=0)) is False
        assert quests.is_weigh_in_day(SUNDAY, AppSettings(reminder_weekday=6)) is True
        assert quests.is_weigh_in_day(WEDNESDAY, AppSettings(reminder_weekday=6)) is False

    def test_none_falls_back_to_default_monday(self) -> None:
        assert quests.is_weigh_in_day(MONDAY, AppSettings(reminder_weekday=None)) is True
        assert quests.is_weigh_in_day(WEDNESDAY, AppSettings(reminder_weekday=None)) is False

    def test_generation_follows_weekday_rule(self) -> None:
        sunday_quests = quests.generate_quests(7, SUNDAY, AppSettings(reminder_weekday=6))
        assert "log_weight" in {q.quest_key for q in sunday_quests}
        monday_quests = quests.generate_quests(7, MONDAY, AppSettings(reminder_weekday=6))
        assert "log_weight" not in {q.quest_key for q in monday_quests}


class TestSeedStability:
    def test_same_inputs_produce_same_rotation(self) -> None:
        settings = AppSettings(reminder_weekday=0)
        first = quests.selected_keys(42, WEDNESDAY, settings)
        second = quests.selected_keys(42, WEDNESDAY, settings)
        assert first == second  # stable across repeated reads the same day
        assert first == [q.quest_key for q in quests.generate_quests(42, WEDNESDAY, settings)]

    def test_different_user_or_date_reranks(self) -> None:
        # Selection is a pure function of (user_id, date, settings): the same
        # rotating pool is ranked by sha256(user:date:key), never Python hash().
        settings = AppSettings(reminder_weekday=0)
        for user_id in (1, 2):
            for day in (WEDNESDAY, MONDAY):
                keys = quests.selected_keys(user_id, day, settings)
                assert len(keys) == 3
                assert keys[0] == "mood_checkin"
                assert set(keys) - {"mood_checkin"} <= set(quests.ROTATION_POOL)


class TestReplaceExclusionsAndCap:
    def test_replacement_excludes_assigned_keys(self) -> None:
        settings = AppSettings(reminder_weekday=0)
        day_keys = set(quests.selected_keys(1, WEDNESDAY, settings))
        ok, key = quests.can_replace(1, WEDNESDAY, day_keys, replaced_count=0)
        assert ok is True
        assert key is not None
        assert key not in day_keys
        # Deterministic: the same day/user/candidates pick the same key.
        ok_again, key_again = quests.can_replace(1, WEDNESDAY, day_keys, replaced_count=0)
        assert (ok_again, key_again) == (ok, key)

    def test_replacement_excludes_previous_replacements(self) -> None:
        day_keys = set(quests.selected_keys(1, WEDNESDAY, AppSettings(reminder_weekday=0)))
        _, first_key = quests.can_replace(1, WEDNESDAY, day_keys, replaced_count=0)
        assert first_key is not None
        assigned_after_first = day_keys | {first_key}
        _, second_key = quests.can_replace(1, WEDNESDAY, assigned_after_first, replaced_count=0)
        assert second_key is not None
        assert second_key not in assigned_after_first

    def test_cap_one_replacement_per_day(self) -> None:
        day_keys = set(quests.selected_keys(1, WEDNESDAY, AppSettings(reminder_weekday=0)))
        ok, key = quests.can_replace(1, WEDNESDAY, day_keys, replaced_count=1)
        assert ok is False
        assert key is None

    def test_no_candidates_when_every_key_assigned(self) -> None:
        all_keys = {entry[0] for entry in QUEST_POOL}
        ok, key = quests.can_replace(1, WEDNESDAY, all_keys, replaced_count=0)
        assert ok is False
        assert key is None


class TestTransitionMatrix:
    def test_done_is_idempotent_and_stamps_completion(self) -> None:
        done = quests.mark_done(_draft(), "2026-08-05 09:00:00")
        assert done.status == "done"
        assert done.completed_at == "2026-08-05 09:00:00"
        # Completing a done quest again is a no-op: same object, same stamp.
        again = quests.mark_done(done, "2026-08-05 12:00:00")
        assert again is done
        assert again.completed_at == "2026-08-05 09:00:00"

    def test_skip_is_terminal_and_clears_completion(self) -> None:
        skipped = quests.mark_skipped(_draft())
        assert skipped.status == "skipped"
        assert skipped.completed_at is None
        assert quests.mark_skipped(skipped) is skipped  # idempotent
        assert quests.is_terminal(skipped) is True

    def test_replace_is_terminal(self) -> None:
        replaced = quests.mark_replaced(_draft())
        assert replaced.status == "replaced"
        assert replaced.completed_at is None
        assert quests.is_terminal(replaced) is True

    def test_policy_guards_for_api(self) -> None:
        open_quest = _draft()
        done_quest = quests.mark_done(_draft(), "2026-08-05 09:00:00")
        skipped_quest = quests.mark_skipped(_draft())
        replaced_quest = quests.mark_replaced(_draft())
        assert quests.is_terminal(open_quest) is False
        assert quests.completion_allowed(open_quest) is True
        assert quests.completion_allowed(done_quest) is True  # 200 no-op
        assert quests.completion_allowed(skipped_quest) is False  # 409
        assert quests.completion_allowed(replaced_quest) is False  # 409
        assert quests.skip_allowed(open_quest) is True
        assert quests.skip_allowed(skipped_quest) is True  # idempotent skip
        assert quests.skip_allowed(done_quest) is False  # 409


class TestDetectionMatrix:
    def test_no_entries_detects_nothing(self) -> None:
        assert quests.detect(QuestDetectionFacts(date=WEDNESDAY.isoformat())) == set()

    def test_weight_row_detects_log_weight(self) -> None:
        facts = QuestDetectionFacts(
            date=WEDNESDAY.isoformat(), has_weight=True, has_any_entry=True
        )
        assert quests.detect(facts) == {"log_weight", "streak_alive"}

    def test_exercise_threshold_is_ten_minutes(self) -> None:
        under = QuestDetectionFacts(date=WEDNESDAY.isoformat(), exercise_min=9)
        at = QuestDetectionFacts(
            date=WEDNESDAY.isoformat(), exercise_min=10, has_any_entry=True
        )
        assert quests.detect(under) == set()
        assert quests.detect(at) == {"exercise_10", "streak_alive"}

    def test_meal_row_detects_log_meal(self) -> None:
        facts = QuestDetectionFacts(
            date=WEDNESDAY.isoformat(), has_meal=True, has_any_entry=True
        )
        assert quests.detect(facts) == {"log_meal", "streak_alive"}

    def test_wellbeing_and_routine_keys_inactive_until_s3a(self) -> None:
        full = QuestDetectionFacts(
            date=WEDNESDAY.isoformat(),
            has_weight=True,
            exercise_min=30,
            has_meal=True,
            has_any_entry=True,
        )
        detected = quests.detect(full)
        assert detected == {"log_weight", "exercise_10", "log_meal", "streak_alive"}
        assert "mood_checkin" not in detected
        assert "habit_checkin" not in detected

    def test_reconcile_marks_detected_open_quests_done(self) -> None:
        day_quests = [
            _draft(key="mood_checkin"),
            _draft(key="exercise_10"),
            _draft(key="log_meal"),
        ]
        facts = QuestDetectionFacts(
            date=WEDNESDAY.isoformat(), exercise_min=30, has_meal=True, has_any_entry=True
        )
        reconciled = quests.reconcile(day_quests, facts)
        assert {q.quest_key: q.status for q in reconciled} == {
            "mood_checkin": "open",  # not auto-detectable in S1a
            "exercise_10": "done",
            "log_meal": "done",
        }
        assert reconciled[1].source == "detected"
        # A manually done quest survives reconcile untouched.
        manual = quests.mark_done(_draft(key="log_meal"), "2026-08-05 08:00:00")
        again = quests.reconcile([manual], facts)
        assert again[0].status == "done"
        assert again[0].source == "rules"


# ---- database-layer persistence (conftest tmp_path DB) ----------------


class TestQuestPersistence:
    def test_insert_quests_persists_and_is_idempotent(self, tmp_path) -> None:
        db = Database(str(tmp_path / "quests.db"))
        db.init_schema()
        try:
            user = make_user(db, "quest-user")
            drafts = quests.generate_quests(
                user.id, WEDNESDAY, AppSettings(reminder_weekday=0)
            )
            rows = db.insert_quests(user.id, WEDNESDAY.isoformat(), drafts)
            assert len(rows) == 3
            assert [r.quest_key for r in rows] == [q.quest_key for q in drafts]
            assert all(r.id > 0 for r in rows)
            assert all(r.status == "open" for r in rows)
            # Regenerating the same day returns the existing rows, no dupes.
            again = db.insert_quests(user.id, WEDNESDAY.isoformat(), drafts)
            assert len(again) == 3
            assert [r.id for r in again] == [r.id for r in rows]
        finally:
            db.close()

    def test_list_quests_for_date_scoped_and_ordered(self, tmp_path) -> None:
        db = Database(str(tmp_path / "quests.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-quests")
            bob = make_user(db, "bob-quests")
            settings = AppSettings(reminder_weekday=0)
            db.insert_quests(alice.id, MONDAY.isoformat(), quests.generate_quests(alice.id, MONDAY, settings))
            db.insert_quests(bob.id, MONDAY.isoformat(), quests.generate_quests(bob.id, MONDAY, settings))
            alice_rows = db.list_quests_for_date(alice.id, MONDAY.isoformat())
            bob_rows = db.list_quests_for_date(bob.id, MONDAY.isoformat())
            assert len(alice_rows) == 3
            assert len(bob_rows) == 3
            # Weigh-in day order: mood_checkin, log_weight, rotating key.
            assert [r.quest_key for r in alice_rows] == quests.selected_keys(alice.id, MONDAY, settings)
            assert [r.quest_key for r in bob_rows] == quests.selected_keys(bob.id, MONDAY, settings)
            # Per-user isolation: each user's list is exactly their own rows.
            assert all(r.id not in {b.id for b in bob_rows} for r in alice_rows)
        finally:
            db.close()

    def test_update_quest_status_scoped_and_stamps(self, tmp_path) -> None:
        db = Database(str(tmp_path / "quests.db"))
        db.init_schema()
        try:
            alice = make_user(db, "alice-status")
            bob = make_user(db, "bob-status")
            date_str = WEDNESDAY.isoformat()
            rows = db.insert_quests(
                alice.id, date_str, quests.generate_quests(alice.id, WEDNESDAY, AppSettings(reminder_weekday=0))
            )
            target = rows[0]
            done = db.update_quest_status(alice.id, target.id, "done", source="manual")
            assert done is not None
            assert done.status == "done"
            assert done.source == "manual"
            assert done.completed_at is not None
            # Cross-user update is hidden (None → 404 at the API) and persists nothing.
            assert db.update_quest_status(bob.id, target.id, "done") is None
            stored = db.list_quests_for_date(alice.id, date_str)
            assert stored[0].status == "done"
            # Skipping clears completed_at.
            skipped = db.update_quest_status(alice.id, rows[1].id, "skipped")
            assert skipped is not None
            assert skipped.status == "skipped"
            assert skipped.completed_at is None
        finally:
            db.close()

    def test_assigned_keys_and_replaced_count(self, tmp_path) -> None:
        db = Database(str(tmp_path / "quests.db"))
        db.init_schema()
        try:
            user = make_user(db, "replace-user")
            date_str = WEDNESDAY.isoformat()
            settings = AppSettings(reminder_weekday=0)
            rows = db.insert_quests(
                user.id, date_str, quests.generate_quests(user.id, WEDNESDAY, settings)
            )
            assigned = db.list_assigned_keys_today(user.id, date_str)
            assert assigned == {r.quest_key for r in rows}
            assert db.count_replaced_today(user.id, date_str) == 0
            # Mark one replaced: cap count rises; the key stays "assigned".
            db.update_quest_status(user.id, rows[0].id, "replaced")
            assert db.count_replaced_today(user.id, date_str) == 1
            assert db.list_assigned_keys_today(user.id, date_str) == assigned
            # Inserting the replacement adds its key to the assigned set.
            ok, new_key = quests.can_replace(user.id, WEDNESDAY, assigned, replaced_count=1)
            assert ok is False  # cap already reached → no key
            ok0, new_key0 = quests.can_replace(user.id, WEDNESDAY, assigned, replaced_count=0)
            assert ok0 is True and new_key0 is not None
            replacement = _draft(key=new_key0)
            db.insert_quests(user.id, date_str, [replacement])
            assert db.list_assigned_keys_today(user.id, date_str) == assigned | {new_key0}
        finally:
            db.close()

    def test_quest_detection_facts(self, tmp_path) -> None:
        db = Database(str(tmp_path / "quests.db"))
        db.init_schema()
        try:
            user = make_user(db, "facts-user")
            date_str = WEDNESDAY.isoformat()
            empty = db.quest_detection_facts(user.id, date_str)
            assert (empty.has_weight, empty.exercise_min, empty.has_meal, empty.has_any_entry) == (
                False,
                0,
                False,
                False,
            )
            db.upsert_entry(user.id, date_str, 80.0)
            db.insert_exercise(user.id, date_str, "walk", 6)
            db.insert_exercise(user.id, date_str, "run", 6)
            db.insert_meal(user.id, date_str, 500.0)
            facts = db.quest_detection_facts(user.id, date_str)
            assert facts.has_weight is True
            assert facts.exercise_min == 12  # summed across the day's rows
            assert facts.has_meal is True
            assert facts.has_any_entry is True
        finally:
            db.close()

    def test_detection_flow_persists_done_status(self, tmp_path) -> None:
        """Entry predates quest render → read-time reconcile marks the mapped
        quest done with source 'detected' (spec scenario, DB layer, no routes)."""
        db = Database(str(tmp_path / "quests.db"))
        db.init_schema()
        try:
            user = make_user(db, "detect-user")
            date_str = WEDNESDAY.isoformat()
            settings = AppSettings(reminder_weekday=2)  # Wednesday = weigh-in day
            rows = db.insert_quests(
                user.id, date_str, quests.generate_quests(user.id, WEDNESDAY, settings)
            )
            assert "log_weight" in {r.quest_key for r in rows}
            # The qualifying entry exists before the quests are rendered.
            db.upsert_entry(user.id, date_str, 80.0)
            facts = db.quest_detection_facts(user.id, date_str)
            reconciled = quests.reconcile(rows, facts)
            for q in reconciled:
                if q.status == "done":
                    db.update_quest_status(user.id, q.id, "done", source="detected")
            final = {r.quest_key: r for r in db.list_quests_for_date(user.id, date_str)}
            detected = quests.detect(facts)
            for key, quest_row in final.items():
                assert quest_row.status == ("done" if key in detected else "open")
            assert final["log_weight"].status == "done"
            assert final["log_weight"].source == "detected"
            assert final["log_weight"].completed_at is not None
            assert final["mood_checkin"].status == "open"  # never auto-detected in S1a
        finally:
            db.close()
