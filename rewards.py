"""Pure reward/milestone logic — no I/O, trivially unit-testable."""

from typing import Any, Optional, Sequence

from models import ActiveCheckpoint, AppSettings, RewardState, WeightEntry
from units import resolve_target_kg


CHECKPOINTS: tuple[int, ...] = (10, 25, 50, 75, 100)


def newly_earned_checkpoints(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """after − before by checkpoint_percent, on the row dicts returned by
    ``list_active_rewards``. Returns the after-dicts whose percent is not in
    before — empty when nothing was newly earned (idempotent re-POST,
    revoke-only, or a same-event revoke+re-earn of the same percent)."""
    before_pct = {r["checkpoint_percent"] for r in before}
    return [r for r in after if r["checkpoint_percent"] not in before_pct]


def checkpoint_thresholds(
    start: Optional[float], target: Optional[float]
) -> list[tuple[int, float]]:
    """Threshold kg for every checkpoint, or [] when progress data is missing
    or the target is not below the start."""
    if start is None or target is None or target >= start:
        return []
    total_loss = start - target
    return [
        (percent, round(start - percent / 100.0 * total_loss, 4))
        for percent in CHECKPOINTS
    ]


def active_checkpoints(
    start: Optional[float], target: Optional[float], current: Optional[float]
) -> list[tuple[int, float]]:
    """Checkpoints whose threshold the latest-dated weight has reached (<=)."""
    if current is None:
        return []
    return [
        (percent, threshold)
        for percent, threshold in checkpoint_thresholds(start, target)
        if current <= threshold
    ]


def next_checkpoint(
    start: Optional[float], target: Optional[float], current: Optional[float]
) -> Optional[tuple[int, float]]:
    """First checkpoint threshold not yet reached, or None when all are active."""
    if current is None:
        return None
    for percent, threshold in checkpoint_thresholds(start, target):
        if current > threshold:
            return (percent, threshold)
    return None


def progress_to_next_checkpoint(
    start: Optional[float], target: Optional[float], current: Optional[float]
) -> float:
    """Band progress 0..1 from the last earned threshold (or start) to the next
    checkpoint; 1.0 once every checkpoint is earned."""
    if current is None or start is None or target is None or target >= start:
        return 0.0
    thresholds = checkpoint_thresholds(start, target)
    if not thresholds:
        return 0.0
    if current <= target:
        return 1.0
    prev = start
    for percent, threshold in thresholds:
        if current <= threshold:
            prev = threshold
        else:
            band = prev - threshold
            if band <= 0:
                return 0.0
            return round(max(0.0, min(1.0, (prev - current) / band)), 4)
    return 0.0


def reward_state(
    entries: Sequence[WeightEntry], settings: AppSettings
) -> RewardState:
    """Derive the complete checkpoint state from entries and settings."""
    start = compute_baseline(entries, settings.start_weight_override)
    current = compute_current(entries)
    target = resolve_target_kg(
        settings.target_weight, settings.target_bmi, settings.height_cm
    )
    active = [
        ActiveCheckpoint(percent=percent, threshold_kg=threshold)
        for percent, threshold in active_checkpoints(start, target, current)
    ]
    return RewardState(
        start_kg=start,
        target_kg=target,
        current_kg=current,
        active=active,
        earned_count=len(active),
        next_checkpoint=next_checkpoint(start, target, current),
        progress_to_next=progress_to_next_checkpoint(start, target, current),
    )


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


def remaining_to_target(
    current: Optional[float], target: Optional[float]
) -> Optional[float]:
    """Kg still to lose to reach the target; None when either is unset."""
    if current is None or target is None:
        return None
    return current - target
