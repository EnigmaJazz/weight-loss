"""Pure collectibles-engine tests (PR 4 · S4): pins R11/R13 — catalogue
order, checkpoint earliest-crossing never relocking, broken meal runs,
retroactive weekly tokens (no activation gate), non-meal streaks, all-locked
empty state."""

from typing import Optional

from models import (
    AchievementFacts,
    AchievementQuestFact,
    AppSettings,
    CollectibleFacts,
    MomentumDayFacts,
    WeightEntry,
)
from constants import COLLECTIBLE_CATALOG
import collectibles
import streaks

def _weight(day: str, kg: float) -> WeightEntry:
    return WeightEntry(id=0, date=day, weight_kg=kg, created_at="")

def _quest(day: str, key: str = "exercise_10") -> AchievementQuestFact:
    return AchievementQuestFact(date=day, quest_key=key, domain="exercise")

def _good(day: str) -> MomentumDayFacts:
    return MomentumDayFacts(date=day, assigned_quests=1, done_quests=1)

def _facts(
    *,
    weights: Optional[list[WeightEntry]] = None,
    meals: Optional[list[str]] = None,
    settings: Optional[AppSettings] = None,
    done_quests: Optional[list[AchievementQuestFact]] = None,
    momentum_days: Optional[list[MomentumDayFacts]] = None,
) -> CollectibleFacts:
    return CollectibleFacts(
        achievement=AchievementFacts(
            done_quests=done_quests or [], momentum_days=momentum_days or []
        ),
        weights=weights or [],
        settings=settings,
        meal_days=meals or [],
    )

def _by_key(facts: CollectibleFacts) -> dict[str, collectibles.CollectibleState]:
    return {s.key: s for s in collectibles.states(facts, COLLECTIBLE_CATALOG)}

def test_catalogue_order_and_empty_all_locked() -> None:
    # R11 order: 6 families, 5 checkpoints, 3 meal milestones, 2 weekly.
    assert COLLECTIBLE_CATALOG == (
        ("getting_started", "Getting Started"), ("moving_forward", "Moving Forward"),
        ("consistency", "Consistency"), ("comeback", "Comeback"),
        ("explorer", "Explorer"), ("personal_best", "Personal Best"),
        ("checkpoint_10", "10% Checkpoint"), ("checkpoint_25", "25% Checkpoint"),
        ("checkpoint_50", "50% Checkpoint"), ("checkpoint_75", "75% Checkpoint"),
        ("checkpoint_100", "100% Checkpoint"), ("meal_7", "7-Day Meal Streak"),
        ("meal_30", "30-Day Meal Streak"), ("meal_100", "100-Day Meal Streak"),
        ("weekly_quests", "Weekly Quests"), ("weekly_good_days", "Weekly Good Days"),
    )
    states = collectibles.states(_facts(), COLLECTIBLE_CATALOG)
    assert [s.key for s in states] == [k for k, _ in COLLECTIBLE_CATALOG]
    assert [s.title for s in states] == [t for _, t in COLLECTIBLE_CATALOG]
    assert all(not s.earned and s.unlocked_at is None for s in states)
    # Family dates reuse achievements.states: one done quest unlocks Getting
    # Started; Moving Forward still needs ten exercise_10 quests (R11).
    states = _by_key(_facts(done_quests=[_quest("2026-07-01")]))
    assert states["getting_started"].unlocked_at == "2026-07-01"
    assert states["moving_forward"].earned is False

def test_checkpoint_first_crossing_wins_and_never_relocks() -> None:
    # R13: crosses 50% (90 kg), rises above, crosses again — the 50% token
    # stays at the FIRST crossing; the deeper 84 kg later earns 75%.
    weights = [
        _weight("2026-07-01", 100.0), _weight("2026-07-10", 90.0),
        _weight("2026-07-20", 95.0), _weight("2026-08-01", 84.0),
    ]
    states = _by_key(_facts(weights=weights, settings=AppSettings(target_weight=80.0)))
    assert states["checkpoint_50"].unlocked_at == "2026-07-10"
    assert states["checkpoint_75"].unlocked_at == "2026-08-01"
    assert states["checkpoint_100"].earned is False  # 80 never reached
    no_settings = _by_key(_facts(weights=[_weight("2026-07-01", 90.0)]))
    assert no_settings["checkpoint_10"].earned is False  # no target -> no thresholds
    no_history = _by_key(_facts(settings=AppSettings(target_weight=80.0)))
    assert no_history["checkpoint_10"].earned is False  # no baseline

def test_meal_milestones_forward_walk_and_broken_runs() -> None:
    # Direct pin on the new streaks forward walk; R13 broken runs: a 29-day
    # break then a 30-day run — the token lands on the later run's day 30
    # and stays earned after another break.
    assert streaks.first_run_milestones(
        [f"2026-01-{d:02d}" for d in range(1, 8)], (7, 30, 100)
    ) == {7: "2026-01-07"}
    assert streaks.first_run_milestones([], (7, 30, 100)) == {}
    days = (
        [f"2026-01-{d:02d}" for d in range(1, 30)]
        + [f"2026-03-{d:02d}" for d in range(1, 31)]
        + [f"2026-05-{d:02d}" for d in range(1, 8)]
    )
    states = _by_key(_facts(meals=days))
    assert states["meal_7"].unlocked_at == "2026-01-07"  # earliest run
    assert states["meal_30"].unlocked_at == "2026-03-30"  # later run's day 30
    assert states["meal_100"].earned is False
    # R11: weight history without a meal-day run must not unlock meal tokens.
    weights = [_weight(d, 90.0) for d in ("2026-07-01", "2026-07-02", "2026-07-03")]
    states = _by_key(_facts(weights=weights))
    assert states["meal_7"].earned is False
    assert states["meal_30"].earned is False
    assert states["meal_100"].earned is False

def test_weekly_earliest_qualifying_week_no_activation_gate() -> None:
    # R13: pre-activation qualifying weeks still earn, at the EARLIEST week
    # (retroactive; a later qualifying week never duplicates it).
    done = [_quest(d) for d in ("2026-07-06",) * 2 + ("2026-07-07",) * 2 + ("2026-07-08",) * 2 + ("2026-07-09",) * 2 + ("2026-07-10",) * 2] + [_quest(f"2026-07-{d:02d}") for d in range(13, 19)]
    days = [_good(d) for d in ("2026-07-06", "2026-07-07", "2026-07-08")]
    states = _by_key(_facts(done_quests=done, momentum_days=days))
    assert states["weekly_quests"].unlocked_at == "2026-07-06"
    assert states["weekly_good_days"].unlocked_at == "2026-07-06"
    # Below target: 2 done quests (< 10) and 2 good days (< 3) stay locked.
    states = _by_key(_facts(
        done_quests=[_quest(d) for d in ("2026-07-06", "2026-07-07")],
        momentum_days=[_good(d) for d in ("2026-07-06", "2026-07-07")],
    ))
    assert states["weekly_quests"].earned is False
    assert states["weekly_good_days"].earned is False
