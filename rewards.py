"""Pure reward/milestone logic — no I/O, trivially unit-testable."""

from typing import Optional, Sequence

from models import WeightEntry


def compute_baseline(
    entries: Sequence[WeightEntry], start_weight_override: Optional[float]
) -> Optional[float]:
    """Starting weight: the override wins, else the first (oldest) entry."""
    if start_weight_override is not None:
        return start_weight_override
    if not entries:
        return None
    return min(entries, key=lambda entry: entry.date).weight_kg


def compute_current(entries: Sequence[WeightEntry]) -> Optional[float]:
    """Latest weight = the most recent entry by date."""
    if not entries:
        return None
    return max(entries, key=lambda entry: entry.date).weight_kg


def compute_lost(
    baseline: Optional[float], current: Optional[float]
) -> Optional[float]:
    """Total weight lost so far; None when data is missing."""
    if baseline is None or current is None:
        return None
    return baseline - current


def milestone_levels(lost: float, step: float) -> list[float]:
    """All milestone levels fully earned for the given lost amount."""
    if step <= 0 or lost <= 0:
        return []
    count = int(lost // step)
    return [round(step * level_index, 4) for level_index in range(1, count + 1)]


def next_milestone(lost: Optional[float], step: float) -> Optional[float]:
    """The next milestone level to earn, or None when step is invalid."""
    if lost is None or step <= 0:
        return None
    effective = max(lost, 0.0)
    return round(step * (int(effective // step) + 1), 4)


def progress_to_next(lost: Optional[float], step: float) -> float:
    """Fraction (0..1) of the way from the last earned milestone to the next."""
    if lost is None or step <= 0:
        return 0.0
    effective = max(lost, 0.0)
    nxt = next_milestone(lost, step) or step
    last_earned = round(nxt - step, 4)
    return round(max(0.0, min(1.0, (effective - last_earned) / step)), 4)


def remaining_to_target(
    current: Optional[float], target: Optional[float]
) -> Optional[float]:
    """Kg still to lose to reach the target; None when either is unset."""
    if current is None or target is None:
        return None
    return current - target
