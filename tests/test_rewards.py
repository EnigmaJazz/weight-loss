"""Unit tests for pure reward/milestone logic (no I/O)."""

from models import WeightEntry
from rewards import (
    compute_baseline,
    compute_current,
    compute_lost,
    milestone_levels,
    next_milestone,
    progress_to_next,
    remaining_to_target,
)


def _entry(date: str, weight_kg: float) -> WeightEntry:
    return WeightEntry(id=1, date=date, weight_kg=weight_kg, created_at="2026-01-01 00:00:00")


ENTRIES = [
    _entry("2026-08-01", 90.5),
    _entry("2026-08-02", 89.7),
    _entry("2026-08-03", 89.0),
]


def test_baseline_from_first_entry():
    assert compute_baseline(ENTRIES, None) == 90.5


def test_baseline_uses_oldest_date():
    unordered = list(reversed(ENTRIES))
    assert compute_baseline(unordered, None) == 90.5


def test_start_weight_override_wins():
    assert compute_baseline(ENTRIES, 92.0) == 92.0


def test_baseline_empty_entries():
    assert compute_baseline([], None) is None


def test_current_is_latest_entry():
    assert compute_current(ENTRIES) == 89.0


def test_lost_calculation():
    assert compute_lost(90.5, 89.0) == 1.5
    assert compute_lost(90.5, 92.0) == -1.5


def test_lost_with_missing_data():
    assert compute_lost(None, 89.0) is None
    assert compute_lost(90.5, None) is None


def test_milestone_levels():
    assert milestone_levels(0.8, 1.0) == []
    assert milestone_levels(1.0, 1.0) == [1.0]
    assert milestone_levels(2.3, 1.0) == [1.0, 2.0]
    assert milestone_levels(3.0, 0.5) == [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def test_milestone_levels_negative():
    assert milestone_levels(-1.0, 1.0) == []
    assert milestone_levels(2.0, 0.0) == []


def test_next_milestone():
    assert next_milestone(0.0, 1.0) == 1.0
    assert next_milestone(0.8, 1.0) == 1.0
    assert next_milestone(1.0, 1.0) == 2.0
    assert next_milestone(2.3, 1.0) == 3.0
    assert next_milestone(0.2, 0.5) == 0.5
    assert next_milestone(None, 1.0) is None


def test_progress_to_next():
    assert progress_to_next(0.0, 1.0) == 0.0
    assert progress_to_next(0.8, 1.0) == 0.8
    assert progress_to_next(1.0, 1.0) == 0.0
    assert progress_to_next(1.4, 1.0) == 0.4
    assert progress_to_next(-0.5, 1.0) == 0.0
    assert progress_to_next(None, 1.0) == 0.0


def test_remaining_to_target():
    assert remaining_to_target(89.0, 80.0) == 9.0
    assert remaining_to_target(89.0, None) is None
    assert remaining_to_target(None, 80.0) is None
