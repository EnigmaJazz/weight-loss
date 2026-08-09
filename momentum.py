"""Pure momentum engine — no I/O, trivially unit-testable (mirrors
rewards.py/streaks.py/xp.py).

Momentum classifies each local calendar date into an engagement tier from
per-date facts (done quests, current assignments, log rows) and derives the
trailing 21-day successful-day window. Everything derives from the quest and
log tables on read; nothing is ever persisted.
"""

from datetime import date, timedelta
from typing import Sequence

from models import MomentumDayFacts, MomentumState

# The trailing window: today minus 20 days through today (inclusive).
WINDOW_DAYS = 21

# Tier display values per the momentum spec.
TIER_NONE = "none"
TIER_SPARK = "Spark"
TIER_GOOD = "Good Day"
TIER_GREAT = "Great Day"

_SUCCESSFUL_TIERS: frozenset[str] = frozenset({TIER_GOOD, TIER_GREAT})


def action_count(facts: MomentumDayFacts) -> int:
    """Total actions for one date: done quests plus the user's log rows
    (weight/exercise/meal/mood/habit). Each quest and row counts once (row
    count, not distinct dates); database.py gathers the mood/habit rows."""
    return facts.done_quests + facts.log_rows


def classify_day(facts: MomentumDayFacts) -> str:
    """The engagement tier for one date per the momentum spec:

    - no current assignment (all rows replaced) -> ``none``, regardless of logs;
    - every current assignment done and at least one action -> ``Great Day``
      (takes precedence over the lower tiers);
    - at least two actions -> ``Good Day``;
    - at least one action -> ``Spark``;
    - otherwise -> ``none``.

    A skipped quest is assigned but not done, so it blocks Great Day; done
    quests count as actions, so a fully-done day is Great even with no logs.
    """
    if facts.assigned_quests == 0:
        return TIER_NONE
    actions = action_count(facts)
    if actions >= 1 and facts.done_quests == facts.assigned_quests:
        return TIER_GREAT
    if actions >= 2:
        return TIER_GOOD
    if actions >= 1:
        return TIER_SPARK
    return TIER_NONE


def is_successful(tier: str) -> bool:
    """Good Day and Great Day are successful; Spark and none are not."""
    return tier in _SUCCESSFUL_TIERS


def window_dates(today: date, days: int = WINDOW_DAYS) -> list[date]:
    """The trailing window of local calendar dates ending ``today`` (inclusive):
    today-(days-1) through today, ascending. Defaults to the 21-day spec
    window."""
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def momentum_state(
    facts: Sequence[MomentumDayFacts], today: date
) -> MomentumState:
    """Derive the full momentum response from one user's per-date facts.

    Only dates inside the trailing 21-day window ending ``today`` (inclusive)
    contribute; window dates without facts resolve to ``none`` (no quests
    assigned that day). ``successful_days`` recounts Good/Great days from the
    window dates, so days outside the window never count.
    """
    by_date = {fact.date: fact for fact in facts}
    tiers: dict[str, str] = {}
    for day in window_dates(today, WINDOW_DAYS):
        day_str = day.isoformat()
        day_facts = by_date.get(day_str)
        if day_facts is None:
            day_facts = MomentumDayFacts(date=day_str)
        tiers[day_str] = classify_day(day_facts)
    today_tier = tiers[today.isoformat()]
    return MomentumState(
        today_tier=today_tier,
        successful_days=sum(1 for tier in tiers.values() if is_successful(tier)),
        window_days=WINDOW_DAYS,
        is_successful_today=is_successful(today_tier),
    )
