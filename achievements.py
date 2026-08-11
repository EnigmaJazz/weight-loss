"""Pure achievements engine — no I/O, trivially unit-testable (mirrors
momentum.py/rewards.py).

Derives the six behaviour-milestone states from one user's gathered facts:
done quest rows (using ``quest.date``), per-date momentum facts (Consistency
and Comeback via momentum.classify_day / is_successful / action_count), and
per-date exercise sums (Personal Best). Missing and replaced-only dates are
neutral. Nothing is ever persisted.
"""

from datetime import date, timedelta
from typing import Optional, Sequence

import momentum
from models import (
    AchievementFacts,
    AchievementState,
    ExerciseDayFacts,
    MomentumDayFacts,
)

CONSISTENCY_WINDOW_DAYS = 7
CONSISTENCY_SUCCESSES = 5
COMEBACK_INACTIVE_RUN = 3
EXPLORER_DOMAINS = 5
MOVING_FORWARD_QUEST_KEY = "exercise_10"
MOVING_FORWARD_QUESTS = 10


def _calendar_dates(start: str, end: str) -> list[str]:
    """Every local ISO date from ``start`` through ``end`` inclusive."""
    day = date.fromisoformat(start)
    last = date.fromisoformat(end)
    dates: list[str] = []
    while day <= last:
        dates.append(day.isoformat())
        day += timedelta(days=1)
    return dates


def first_done_quest_date(facts: AchievementFacts) -> Optional[str]:
    """Earliest done quest date, or None (Getting Started)."""
    if not facts.done_quests:
        return None
    return min(quest.date for quest in facts.done_quests)


def tenth_exercise_date(facts: AchievementFacts) -> Optional[str]:
    """Date of the tenth done ``exercise_10`` quest, or None (Moving Forward);
    only ``exercise_10`` qualifiers count, in date order."""
    qualifiers = sorted(
        quest.date
        for quest in facts.done_quests
        if quest.quest_key == MOVING_FORWARD_QUEST_KEY
    )
    if len(qualifiers) < MOVING_FORWARD_QUESTS:
        return None
    return qualifiers[MOVING_FORWARD_QUESTS - 1]


def five_domains_date(facts: AchievementFacts) -> Optional[str]:
    """Date of the fifth first-seen domain among done quests, or None
    (Explorer)."""
    seen: set[str] = set()
    for quest in sorted(facts.done_quests, key=lambda q: q.date):
        seen.add(quest.domain)
        if len(seen) == EXPLORER_DOMAINS:
            return quest.date
    return None


def consistency_date(facts: AchievementFacts) -> Optional[str]:
    """Date of the fifth success in the earliest seven-date window holding
    five successful days, or None (Consistency); missing and replaced-only
    dates are neutral."""
    by_date = {day.date: day for day in facts.momentum_days}
    if not by_date:
        return None
    days = _calendar_dates(min(by_date), max(by_date))
    for start in range(len(days) - CONSISTENCY_WINDOW_DAYS + 1):
        window = days[start : start + CONSISTENCY_WINDOW_DAYS]
        successes = [
            day
            for day in window
            if momentum.is_successful(
                momentum.classify_day(by_date.get(day, MomentumDayFacts(date=day)))
            )
        ]
        if len(successes) >= CONSISTENCY_SUCCESSES:
            return successes[CONSISTENCY_SUCCESSES - 1]
    return None


def comeback_date(facts: AchievementFacts) -> Optional[str]:
    """Earliest action date immediately after three consecutive inactive
    dates, or None (Comeback). Inactive = assigned quests with zero actions
    (skipped counts as assigned); missing and replaced-only dates break the
    run. A return needs at least one action (Spark or better)."""
    by_date = {day.date: day for day in facts.momentum_days}
    if not by_date:
        return None
    days = _calendar_dates(min(by_date), max(by_date))

    def fact(day: str) -> MomentumDayFacts:
        return by_date.get(day, MomentumDayFacts(date=day))

    for index in range(COMEBACK_INACTIVE_RUN, len(days)):
        run = days[index - COMEBACK_INACTIVE_RUN : index]
        if all(
            fact(day).assigned_quests > 0 and momentum.action_count(fact(day)) == 0
            for day in run
        ) and momentum.action_count(fact(days[index])) >= 1:
            return days[index]
    return None


def personal_best_date(facts: AchievementFacts) -> Optional[str]:
    """Earliest date whose summed exercise minutes exceed every strictly
    earlier sum, or None (Personal Best); zero is the empty pre-history
    baseline, so the first positive day qualifies. Re-locks when no positive
    evidence remains (derived on read)."""
    best = 0
    for day in sorted(facts.exercise_days, key=lambda entry: entry.date):
        if day.duration_min > best:
            return day.date
        best = max(best, day.duration_min)
    return None


def states(facts: AchievementFacts, catalog: Sequence[tuple[str, str]]) -> list[AchievementState]:
    """Derive one AchievementState per catalogue entry, in catalogue order;
    ``unlocked_at`` is the earliest qualifying local ISO date, or None."""
    dates: dict[str, Optional[str]] = {
        "getting_started": first_done_quest_date(facts),
        "moving_forward": tenth_exercise_date(facts),
        "consistency": consistency_date(facts),
        "comeback": comeback_date(facts),
        "explorer": five_domains_date(facts),
        "personal_best": personal_best_date(facts),
    }
    return [
        AchievementState(
            key=key,
            title=title,
            earned=dates[key] is not None,
            unlocked_at=dates[key],
        )
        for key, title in catalog
    ]
