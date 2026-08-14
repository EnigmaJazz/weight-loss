"""Pure collectibles engine — no I/O (mirrors achievements/rewards/streaks).

Derives the 16 cosmetic tokens (R11) from one snapshot: six achievement-family
dates (achievements.states), five checkpoint earliest-crossing dates, three
meal-day milestones (streaks.first_run_milestones), and two weekly tokens from
full-history week facts, no activation gate (R13). Cosmetic only (R10)."""

from datetime import date
from typing import Optional, Sequence

from constants import ACHIEVEMENTS
from models import (
    AchievementFacts,
    CollectibleFacts,
    CollectibleState,
    MomentumDayFacts,
    WeightEntry,
)
import achievements
import rewards
import streaks
import weekly
from units import resolve_target_kg

MEAL_MILESTONES: tuple[int, ...] = (7, 30, 100)


def checkpoint_dates(
    weights: Sequence[WeightEntry], start: Optional[float], target: Optional[float]
) -> dict[int, str]:
    """Earliest weight date at/below each threshold kg, by percent; the first
    crossing wins and never relocks (R13). Empty without data/thresholds."""
    result: dict[int, str] = {}
    for percent, threshold in rewards.checkpoint_thresholds(start, target):
        crossing = min((e for e in weights if e.weight_kg <= threshold), key=lambda e: e.date, default=None)
        if crossing is not None:
            result[percent] = crossing.date
    return result


def weekly_token_dates(facts: AchievementFacts) -> dict[str, str]:
    """Earliest week (Monday ISO date) meeting each objective across full
    history — pre-activation weeks qualify (R9/R13), earliest wins once."""
    quest_counts: dict[str, int] = {}
    for quest in facts.done_quests:
        week = weekly.week_start(date.fromisoformat(quest.date)).isoformat()
        quest_counts[week] = quest_counts.get(week, 0) + 1
    by_week: dict[str, list[MomentumDayFacts]] = {}
    for day in facts.momentum_days:
        week = weekly.week_start(date.fromisoformat(day.date)).isoformat()
        by_week.setdefault(week, []).append(day)
    good_counts = {week: weekly.good_day_count(days, date.fromisoformat(week)) for week, days in by_week.items()}
    result: dict[str, str] = {}
    for goal in weekly.WEEK_GOALS:
        counts = quest_counts if goal == "quests" else good_counts
        qualifying = [w for w, n in counts.items() if weekly.goal_met(goal, n)]
        if qualifying:
            result[goal] = min(qualifying)
    return result


def token_dates(facts: CollectibleFacts) -> dict[str, Optional[str]]:
    """Every catalogue key -> earliest historical unlock date (None locked)."""
    family = {s.key: s.unlocked_at for s in achievements.states(facts.achievement, ACHIEVEMENTS)}
    settings = facts.settings
    start = (
        rewards.compute_baseline(facts.weights, settings.start_weight_override)
        if settings is not None else None
    )
    target = (
        resolve_target_kg(settings.target_weight, settings.target_bmi, settings.height_cm)
        if settings is not None else None
    )
    checkpoints = {
        f"checkpoint_{p}": d for p, d in checkpoint_dates(facts.weights, start, target).items()
    }
    meals = {f"meal_{m}": d for m, d in streaks.first_run_milestones(facts.meal_days, MEAL_MILESTONES).items()}
    weekly_tokens = {f"weekly_{g}": d for g, d in weekly_token_dates(facts.achievement).items()}
    return {**family, **checkpoints, **meals, **weekly_tokens}


def states(
    facts: CollectibleFacts, catalog: Sequence[tuple[str, str]]
) -> list[CollectibleState]:
    """One CollectibleState per catalogue entry, in catalogue order."""
    dates = token_dates(facts)
    return [CollectibleState(key, title, dates.get(key) is not None, dates.get(key)) for key, title in catalog]
