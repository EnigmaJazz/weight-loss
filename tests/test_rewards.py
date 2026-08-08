"""Unit tests for pure reward logic: checkpoint thresholds and active state (no I/O)."""

from typing import Any

from models import AppSettings, WeightEntry
from rewards import (
    CHECKPOINTS,
    active_checkpoints,
    checkpoint_thresholds,
    compute_baseline,
    compute_current,
    compute_lost,
    newly_earned_checkpoints,
    next_checkpoint,
    progress_to_next_checkpoint,
    remaining_to_target,
    reward_state,
)


def _entry(date: str, weight_kg: float) -> WeightEntry:
    return WeightEntry(id=1, date=date, weight_kg=weight_kg, created_at="2026-01-01 00:00:00")


ENTRIES = [
    _entry("2026-08-01", 90.5),
    _entry("2026-08-02", 89.7),
    _entry("2026-08-03", 89.0),
]


# ---- checkpoint thresholds -------------------------------------------------


def test_checkpoint_constants():
    assert CHECKPOINTS == (10, 25, 50, 75, 100)


def test_thresholds_use_earliest_entry_without_override():
    # Spec: start = earliest entry (100 kg), target 80 -> 10% = 98, 100% = 80.
    assert checkpoint_thresholds(100.0, 80.0) == [
        (10, 98.0),
        (25, 95.0),
        (50, 90.0),
        (75, 85.0),
        (100, 80.0),
    ]


def test_thresholds_use_configured_override():
    # Spec: override (110 kg) must be used as start for every checkpoint.
    thresholds = checkpoint_thresholds(110.0, 80.0)
    assert thresholds[0] == (10, 107.0)
    assert thresholds[1] == (25, 102.5)
    assert thresholds[4] == (100, 80.0)


def test_thresholds_missing_data_returns_empty():
    assert checkpoint_thresholds(None, 80.0) == []
    assert checkpoint_thresholds(100.0, None) == []
    assert checkpoint_thresholds(None, None) == []


def test_thresholds_target_at_or_above_start_returns_empty():
    assert checkpoint_thresholds(80.0, 80.0) == []
    assert checkpoint_thresholds(80.0, 90.0) == []


# ---- active reward state ---------------------------------------------------


def test_active_checkpoints_inclusive_equality():
    # Spec: latest weight exactly at threshold (95 kg) -> both checkpoints active.
    assert active_checkpoints(100.0, 80.0, 95.0) == [(10, 98.0), (25, 95.0)]


def test_active_checkpoints_all_earned_at_target():
    active = active_checkpoints(100.0, 80.0, 80.0)
    assert len(active) == 5
    assert active[-1] == (100, 80.0)


def test_active_checkpoints_none_above_first_threshold():
    # Spec: regression above both thresholds revokes both checkpoints.
    assert active_checkpoints(100.0, 80.0, 99.0) == []


def test_active_checkpoints_without_current():
    assert active_checkpoints(100.0, 80.0, None) == []
    assert active_checkpoints(None, 80.0, 90.0) == []


# ---- next checkpoint / band progress ---------------------------------------


def test_next_checkpoint_is_first_unreached():
    assert next_checkpoint(100.0, 80.0, 97.0) == (25, 95.0)
    assert next_checkpoint(100.0, 80.0, 99.0) == (10, 98.0)
    assert next_checkpoint(100.0, 80.0, 79.0) is None


def test_progress_to_next_band():
    assert progress_to_next_checkpoint(100.0, 80.0, 99.0) == 0.5
    assert progress_to_next_checkpoint(100.0, 80.0, 97.0) == 0.3333
    assert progress_to_next_checkpoint(100.0, 80.0, 95.0) == 0.0
    assert progress_to_next_checkpoint(100.0, 80.0, 90.0) == 0.0
    assert progress_to_next_checkpoint(100.0, 80.0, 80.0) == 1.0
    assert progress_to_next_checkpoint(100.0, 80.0, None) == 0.0
    assert progress_to_next_checkpoint(None, 80.0, 90.0) == 0.0


# ---- reward_state composition ----------------------------------------------


def test_reward_state_derives_full_state():
    settings = AppSettings(target_weight=80.0)
    entries = [_entry("2026-08-01", 100.0), _entry("2026-08-02", 95.0)]
    state = reward_state(entries, settings)
    assert state.start_kg == 100.0
    assert state.target_kg == 80.0
    assert state.current_kg == 95.0
    assert [(cp.percent, cp.threshold_kg) for cp in state.active] == [
        (10, 98.0),
        (25, 95.0),
    ]
    assert state.earned_count == 2
    assert state.next_checkpoint == (50, 90.0)
    assert state.progress_to_next == 0.0


def test_reward_state_empty_without_target():
    state = reward_state(ENTRIES, AppSettings())
    assert state.active == []
    assert state.earned_count == 0
    assert state.next_checkpoint is None
    assert state.progress_to_next == 0.0


# ---- shared target resolver (target-progress-rewards) ---------------------


def test_reward_state_resolves_target_from_bmi():
    # Spec: height 175 + target_bmi 22 (resolved 67.4 kg), no target_weight.
    settings = AppSettings(target_bmi=22.0, height_cm=175.0)
    entries = [_entry("2026-08-01", 100.0), _entry("2026-08-02", 95.0)]
    state = reward_state(entries, settings)
    assert state.target_kg == 67.4
    # 10% threshold = 100 - 0.1*32.6 = 96.74; current 95 has earned it.
    assert [(cp.percent, cp.threshold_kg) for cp in state.active] == [(10, 96.74)]


def test_reward_state_weight_precedence_over_bmi():
    # Spec: target_weight 80 wins over target_bmi 22 + height 175.
    settings = AppSettings(target_weight=80.0, target_bmi=22.0, height_cm=175.0)
    entries = [_entry("2026-08-01", 100.0), _entry("2026-08-02", 95.0)]
    state = reward_state(entries, settings)
    assert state.target_kg == 80.0
    assert [(cp.percent, cp.threshold_kg) for cp in state.active] == [
        (10, 98.0),
        (25, 95.0),
    ]


def test_reward_state_null_target_when_unresolvable():
    # Spec: BMI target without height resolves to None -> no checkpoints.
    state = reward_state(ENTRIES, AppSettings(target_bmi=22.0))
    assert state.target_kg is None
    assert state.active == []
    assert state.earned_count == 0


# ---- newly-earned checkpoint diff (checkpoint-celebrations) -----------------


def _reward_row(
    percent: int, threshold_kg: float = 98.0, earned_at: str = "2026-08-01 10:00:00"
) -> dict[str, Any]:
    """One active_rewards row as returned by list_active_rewards."""
    return {
        "checkpoint_percent": percent,
        "threshold_kg": threshold_kg,
        "earned_at": earned_at,
    }


def test_newly_earned_single_earn():
    # Spec: before = {10}, after = {10, 25} -> the diff returns {25}.
    before = [_reward_row(10)]
    after = [_reward_row(10), _reward_row(25, threshold_kg=95.0)]
    assert newly_earned_checkpoints(before, after) == [
        _reward_row(25, threshold_kg=95.0)
    ]


def test_newly_earned_batched_returns_after_rows():
    # Spec: batched earn {10, 25, 50} -> diff returns the after-dicts for 25 and 50.
    before = [_reward_row(10)]
    after = [
        _reward_row(10),
        _reward_row(25, threshold_kg=95.0),
        _reward_row(50, threshold_kg=90.0),
    ]
    assert newly_earned_checkpoints(before, after) == [
        _reward_row(25, threshold_kg=95.0),
        _reward_row(50, threshold_kg=90.0),
    ]


def test_newly_earned_idempotent_repost():
    # Spec: before = after = {10, 25} -> empty diff (idempotent re-POST).
    before = after = [_reward_row(10), _reward_row(25, threshold_kg=95.0)]
    assert newly_earned_checkpoints(before, after) == []


def test_newly_earned_revoke_only():
    # Spec: before = {10, 25}, after = {10} -> empty diff (revoke-only).
    before = [_reward_row(10), _reward_row(25, threshold_kg=95.0)]
    after = [_reward_row(10)]
    assert newly_earned_checkpoints(before, after) == []


def test_newly_earned_same_event_revoke_and_reearn():
    # Spec: before = {25}, after = {25} (revoked then re-earned) -> empty diff:
    # a percent present on both sides is not newly earned, so no double-fire.
    before = [_reward_row(25, threshold_kg=95.0)]
    after = [_reward_row(25, threshold_kg=95.0, earned_at="2026-08-02 09:00:00")]
    assert newly_earned_checkpoints(before, after) == []


def test_newly_earned_revoke_and_earn_different_percent():
    # Same-event revoke + earn of a DIFFERENT percent: 25 present on both sides
    # stays silent, but a fresh 10 in after is newly earned.
    before = [_reward_row(25, threshold_kg=95.0)]
    after = [_reward_row(10), _reward_row(25, threshold_kg=95.0)]
    assert newly_earned_checkpoints(before, after) == [_reward_row(10)]


def test_newly_earned_duplicate_percent_safety():
    # list_active_rewards never yields duplicate percents (UNIQUE constraint),
    # but the diff must stay correct if it ever does: duplicates in before are
    # deduped by the set, and every after-row for a newly-earned percent returns.
    before = [_reward_row(10), _reward_row(10, threshold_kg=98.5)]
    after = [
        _reward_row(10),
        _reward_row(10, threshold_kg=98.5),
        _reward_row(25, threshold_kg=95.0),
        _reward_row(25, threshold_kg=95.0, earned_at="2026-08-02 09:00:00"),
    ]
    assert newly_earned_checkpoints(before, after) == [
        _reward_row(25, threshold_kg=95.0),
        _reward_row(25, threshold_kg=95.0, earned_at="2026-08-02 09:00:00"),
    ]


def test_newly_earned_empty_to_empty():
    assert newly_earned_checkpoints([], []) == []


# ---- preserved baseline helpers (approval: behavior unchanged) -------------


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


def test_remaining_to_target():
    assert remaining_to_target(89.0, 80.0) == 9.0
    assert remaining_to_target(89.0, None) is None
    assert remaining_to_target(None, 80.0) is None
