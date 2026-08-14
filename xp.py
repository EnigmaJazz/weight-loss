"""Pure XP derivation — no I/O, trivially unit-testable (mirrors
quests.py/rewards.py).

Levels follow the normative xp-progression curve: level 1 starts at 0 XP and
advancing from level n costs ``LEVEL_XP_PER_LEVEL + (n-1)*LEVEL_XP_STEP``, so
level L starts at T(L) = 25*(L-1)*(L+2) XP (cumulative). Totals are derived
from done quests plus persisted weekly_awards values (SUM in database.py);
weekly_awards is the only award table and this module never writes or reads a
ledger.
"""

from math import isqrt

from constants import LEVEL_TITLES, LEVEL_XP_PER_LEVEL, LEVEL_XP_STEP


def threshold_for_level(level: int) -> int:
    """Cumulative XP at which ``level`` starts: T(1) = 0 and
    T(L) = sum_{k=1}^{L-1} (LEVEL_XP_PER_LEVEL + (k-1)*LEVEL_XP_STEP)."""
    return (
        LEVEL_XP_PER_LEVEL * (level - 1)
        + LEVEL_XP_STEP * (level - 1) * (level - 2) // 2
    )


def level_from_xp(total_xp: int) -> int:
    """The greatest level L >= 1 whose start threshold is not above
    ``total_xp``.

    This is the integer-exact closed form of the spec's
    floor((sqrt(9 + 4*XP/25) - 1)/2): T(L) <= X <=> (2L+1)^2 <= (4X+225)/25,
    so L = floor((isqrt(4X+225) - 5)/10), clamped to at least 1. ``isqrt``
    keeps exact boundaries exact (no float drift at 100/250/450/...).
    """
    return max(1, (isqrt(225 + 4 * total_xp) - 5) // 10)


def level_progress(total_xp: int) -> tuple[int, int]:
    """(xp_into_next, next_level_at) for ``total_xp``: XP earned into the
    current level and the absolute XP the next level starts at."""
    level = level_from_xp(total_xp)
    return total_xp - threshold_for_level(level), threshold_for_level(level + 1)


def title_for_level(level: int) -> str:
    """The title for ``level``: the last LEVEL_TITLES band whose minimum is
    not above it (level 30+ is Legend)."""
    title = LEVEL_TITLES[0][1]
    for min_level, band_title in LEVEL_TITLES:
        if level >= min_level:
            title = band_title
    return title
