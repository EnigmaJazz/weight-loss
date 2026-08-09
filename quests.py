"""Pure daily-quest engine — no I/O, trivially unit-testable (mirrors
rewards.py/streaks.py).

Quests are generated deterministically from ``(user_id, date)`` via SHA-256
ranking (never Python's process-randomized ``hash()``), persisted by
database.py, and detected as done from log-table facts. Status transitions
are validated by the policy helpers here; the API maps denials to 409 and
the persistence layer stamps the source and completion timestamp.
"""

from datetime import date
from hashlib import sha256
from typing import AbstractSet, Optional, Sequence

from constants import QUEST_POOL
from models import AppSettings, Quest, QuestDetectionFacts

# Every key that can fill the two non-mandatory daily slots: the four rotating
# quests plus the weekly weigh-in. mood_checkin is always assigned and is
# never part of this pool. Rotation itself ranks only the four rotating keys
# (see _rotating_keys); log_weight appears only on weigh-in days.
ROTATION_POOL: frozenset[str] = frozenset(
    entry[0] for entry in QUEST_POOL if entry[0] != "mood_checkin"
)

_POOL_BY_KEY: dict[str, tuple[str, str, str, str, int, str]] = {
    entry[0]: entry for entry in QUEST_POOL
}

_ROTATING_KEYS: tuple[str, ...] = tuple(
    entry[0] for entry in QUEST_POOL if entry[0] not in ("mood_checkin", "log_weight")
)

# DEFAULT_SETTINGS["reminder_weekday"] (Monday), used when a user's schedule
# is unset. Kept as a typed literal so pyright can verify the comparison.
_DEFAULT_REMINDER_WEEKDAY: int = 0


def _rotation_rank(user_id: int, day: date, key: str) -> bytes:
    """Deterministic per-key rotation rank: the SHA-256 digest of
    ``f"{user_id}:{day}:{key}"``. Unlike Python's ``hash()`` this survives
    process restarts, so a day's assignment never changes between reads."""
    return sha256(f"{user_id}:{day.isoformat()}:{key}".encode()).digest()


def _rotating_keys(
    user_id: int, day: date, exclude: AbstractSet[str]
) -> list[str]:
    """The four rotating keys ranked by digest then catalogue order, minus
    ``exclude``. The stable sort keeps catalogue order as the tie-break."""
    return [
        key
        for key in sorted(
            _ROTATING_KEYS, key=lambda key: _rotation_rank(user_id, day, key)
        )
        if key not in exclude
    ]


def is_weigh_in_day(day: date, settings: AppSettings) -> bool:
    """Whether the date's weekday equals the user's resolved reminder_weekday.
    A None schedule falls back to the DEFAULT_SETTINGS Monday."""
    reminder_weekday = (
        settings.reminder_weekday
        if settings.reminder_weekday is not None
        else _DEFAULT_REMINDER_WEEKDAY
    )
    return day.weekday() == reminder_weekday


def selected_keys(user_id: int, day: date, settings: AppSettings) -> list[str]:
    """The day's quest keys in assignment order: mood_checkin, then log_weight
    on weigh-in days, then the highest-ranked rotating keys to reach three.
    Deterministic for a given (user_id, date) and never duplicate within a
    day."""
    picks = ["mood_checkin"]
    if is_weigh_in_day(day, settings):
        picks.append("log_weight")
    picks.extend(_rotating_keys(user_id, day, frozenset())[: 3 - len(picks)])
    return picks


def generate_quests(user_id: int, day: date, settings: AppSettings) -> list[Quest]:
    """The day's three quest drafts (status open, source rules) with catalogue
    metadata, in assignment order. Persistence is database.py's job."""
    return [draft_for_key(key, day) for key in selected_keys(user_id, day, settings)]


def draft_for_key(key: str, day: date) -> Quest:
    """A single open quest draft for one catalogue key (id 0; the persistence
    layer stamps the real id/created_at). Replacement rows can be any rotating
    key not represented by a row that day — not necessarily one of the day's
    originally selected keys — so the route builds them from this."""
    entry = _POOL_BY_KEY[key]
    return Quest(
        id=0,
        date=day.isoformat(),
        quest_key=key,
        domain=entry[1],
        title=entry[2],
        description=entry[3],
        xp_value=entry[4],
        status="open",
        difficulty=entry[5],
        source="rules",
        created_at="",
    )


def can_replace(
    user_id: int,
    day: date,
    assigned_keys: AbstractSet[str],
    replaced_count: int,
) -> tuple[bool, Optional[str]]:
    """Whether a replacement is allowed and which key it would use. Denied
    (False, None) when the one-per-day cap is reached or every rotating key is
    already represented by a row that day; otherwise the highest-ranked
    unassigned rotating key."""
    if replaced_count >= 1:
        return False, None
    ranked = _rotating_keys(user_id, day, assigned_keys)
    if not ranked:
        return False, None
    return True, ranked[0]


def _with_status(
    quest: Quest, status: str, source: str, completed_at: Optional[str]
) -> Quest:
    """A copy of ``quest`` with the new status fields. ``source`` is passed
    through so reconcile can stamp 'detected' while manual transitions keep
    the row's original source until the persistence layer stamps it."""
    return Quest(
        id=quest.id,
        date=quest.date,
        quest_key=quest.quest_key,
        domain=quest.domain,
        title=quest.title,
        description=quest.description,
        xp_value=quest.xp_value,
        status=status,
        difficulty=quest.difficulty,
        source=source,
        created_at=quest.created_at,
        completed_at=completed_at,
    )


def mark_done(quest: Quest, now: str) -> Quest:
    """Idempotent completion: an open quest becomes done with ``now`` as its
    completed_at; an already-done quest is returned unchanged."""
    if quest.status == "done":
        return quest
    return _with_status(quest, "done", quest.source, now)


def mark_skipped(quest: Quest) -> Quest:
    """Terminal skip, zero XP: an open quest becomes skipped with no
    completion timestamp; an already-skipped quest is returned unchanged."""
    if quest.status == "skipped":
        return quest
    return _with_status(quest, "skipped", quest.source, None)


def mark_replaced(quest: Quest) -> Quest:
    """Mark a quest replaced (terminal, no longer current, no XP); the
    replacement row is created separately by the persistence layer."""
    if quest.status == "replaced":
        return quest
    return _with_status(quest, "replaced", quest.source, None)


def is_terminal(quest: Quest) -> bool:
    """Skipped and replaced quests are terminal — they can never become
    current again (done stays idempotently re-completable, so it is not
    terminal)."""
    return quest.status in ("skipped", "replaced")


def completion_allowed(quest: Quest) -> bool:
    """Open quests complete; done quests complete idempotently (200 no-op);
    skipped/replaced quests are 409."""
    return quest.status in ("open", "done")


def skip_allowed(quest: Quest) -> bool:
    """Open quests skip; skipped quests skip idempotently; done/replaced
    quests are 409."""
    return quest.status in ("open", "skipped")


def detect(facts: QuestDetectionFacts) -> set[str]:
    """The quest keys whose completion the given facts prove. Every catalogue
    key maps to a fact: weight row, exercise sum >= 10, meal row, mood row,
    habit row, or any qualifying entry row (streak_alive). The mood/habit
    facts are gathered by database.py; has_habit is HABIT_TYPES-driven there,
    so a catalogue change propagates to detection without touching this
    mapping."""
    detected: set[str] = set()
    if facts.has_weight:
        detected.add("log_weight")
    if facts.exercise_min >= 10:
        detected.add("exercise_10")
    if facts.has_meal:
        detected.add("log_meal")
    if facts.has_mood:
        detected.add("mood_checkin")
    if facts.has_habit:
        detected.add("habit_checkin")
    if facts.has_any_entry:
        detected.add("streak_alive")
    return detected


def reconcile(quests: Sequence[Quest], facts: QuestDetectionFacts) -> list[Quest]:
    """Return quest copies with open quests whose key the facts detect marked
    done (source 'detected'; the completion timestamp is stamped by the
    persistence layer). Every other quest passes through untouched."""
    detected = detect(facts)
    updated: list[Quest] = []
    for quest in quests:
        if quest.status == "open" and quest.quest_key in detected:
            updated.append(_with_status(quest, "done", "detected", None))
        else:
            updated.append(quest)
    return updated
