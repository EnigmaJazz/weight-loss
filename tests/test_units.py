"""Unit tests for pure kg/lb/stone/BMI conversion helpers (no I/O)."""

import pytest

from models import WeightDisplay
from units import calculate_bmi, kg_to_lb, kg_to_stone, weight_display


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
