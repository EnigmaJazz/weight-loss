"""Unit tests for pure kg/lb/stone/BMI conversion helpers (no I/O)."""

import pytest

from models import WeightDisplay
from units import (
    calculate_bmi,
    classify_bmi,
    healthy_weight_range,
    kg_to_lb,
    kg_to_stone,
    resolve_target_kg,
    weight_display,
    weight_kg_from_bmi,
)


def test_kg_to_lb_uses_spec_factor():
    # Spec: total lb MUST equal kg x 2.2046226218.
    assert kg_to_lb(70.0) == pytest.approx(154.323583526)
    assert kg_to_lb(100.0) == pytest.approx(220.46226218)


def test_kg_to_stone_decomposes_into_whole_and_remaining_lb():
    # Spec: whole stone = floor(total lb / 14), remaining lb = total lb - 14 * whole.
    whole, remaining = kg_to_stone(70.0)
    assert whole == 11
    assert remaining == pytest.approx(0.323583526)


def test_kg_to_stone_below_one_stone():
    whole, remaining = kg_to_stone(1.0)
    assert whole == 0
    assert remaining == pytest.approx(2.2046226218)


def test_kg_to_stone_is_consistent_with_kg_to_lb():
    # Triangulation: decomposition must add back to the exact lb value.
    for weight_kg in (55.0, 89.7, 120.5):
        whole, remaining = kg_to_stone(weight_kg)
        assert whole * 14 + remaining == pytest.approx(kg_to_lb(weight_kg))


def test_bmi_with_configured_height():
    # Spec: 70 kg, 175 cm -> 70 / (1.75)^2 = 22.857142... before rounding.
    assert calculate_bmi(70.0, 175.0) == pytest.approx(22.857142857142858)


def test_bmi_without_height_is_none():
    # Spec: height unset -> every BMI display is em dash.
    assert calculate_bmi(70.0, None) is None


def test_bmi_with_nonpositive_height_is_none():
    assert calculate_bmi(70.0, 0.0) is None
    assert calculate_bmi(70.0, -10.0) is None


def test_weight_display_builds_typed_view():
    view = weight_display(70.0, 175.0)
    assert isinstance(view, WeightDisplay)
    assert view.weight_kg == 70.0
    assert view.lb == pytest.approx(154.323583526)
    assert view.stone == 11
    assert view.stone_lb == pytest.approx(0.323583526)
    assert view.bmi == pytest.approx(22.857142857142858)


def test_weight_display_bmi_none_when_height_missing():
    view = weight_display(70.0, None)
    assert view.bmi is None
    assert view.stone == 11


# ---- BMI target helpers (bmi-goal-setting) -------------------------------


def test_weight_kg_from_bmi_both_set():
    # Spec: round(bmi * (h/100)^2, 1); 22.0 BMI at 175 cm -> 67.4 kg.
    assert weight_kg_from_bmi(22.0, 175.0) == 67.4


def test_weight_kg_from_bmi_boundary():
    # Spec: 18.5 BMI at 200 cm -> exactly 74.0 kg.
    assert weight_kg_from_bmi(18.5, 200.0) == 74.0


def test_weight_kg_from_bmi_unset_is_none():
    assert weight_kg_from_bmi(None, 175.0) is None
    assert weight_kg_from_bmi(22.0, None) is None
    assert weight_kg_from_bmi(None, None) is None


def test_healthy_weight_range_with_height():
    # Spec formula: (round(18.5*(h/100)**2, 1), round(24.9*(h/100)**2, 1)).
    # NOTE: the spec scenario's (56.6, 76.2) contradicts its own formula;
    # round(18.5*1.75^2, 1) is 56.7 and round(24.9*1.75^2, 1) is 76.3.
    assert healthy_weight_range(175.0) == (56.7, 76.3)


def test_healthy_weight_range_without_height_is_none():
    assert healthy_weight_range(None) is None


def test_classify_bmi_boundaries():
    # Spec: 18.5 and 24.9 are healthy; 25.0 is overweight.
    assert classify_bmi(18.5) == "healthy"
    assert classify_bmi(24.9) == "healthy"
    assert classify_bmi(25.0) == "overweight"


def test_classify_bmi_underweight():
    assert classify_bmi(18.4) == "underweight"


def test_resolve_target_kg_weight_wins():
    # Spec: target_weight takes precedence over the BMI-derived target.
    assert resolve_target_kg(80.0, 22.0, 175.0) == 80.0


def test_resolve_target_kg_derives_from_bmi():
    assert resolve_target_kg(None, 22.0, 175.0) == 67.4


def test_resolve_target_kg_none_semantics():
    # Either BMI input unset -> None; fully unset -> None.
    assert resolve_target_kg(None, 22.0, None) is None
    assert resolve_target_kg(None, None, 175.0) is None
    assert resolve_target_kg(None, None, None) is None
    # An explicit weight target needs neither BMI input.
    assert resolve_target_kg(80.0, None, None) == 80.0
