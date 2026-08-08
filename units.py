"""Pure unit conversions and display-view construction — no I/O."""

from typing import Optional

from models import WeightDisplay

# Spec: total lb = kg x 2.2046226218.
KG_TO_LB = 2.2046226218

STONE_LB = 14


def kg_to_lb(weight_kg: float) -> float:
    """Convert kilograms to pounds using the spec factor."""
    return weight_kg * KG_TO_LB


def kg_to_stone(weight_kg: float) -> tuple[int, float]:
    """Decompose kilograms into (whole stone, remaining lb)."""
    total_lb = kg_to_lb(weight_kg)
    whole = int(total_lb // STONE_LB)
    remaining = total_lb - STONE_LB * whole
    return whole, remaining


def calculate_bmi(weight_kg: float, height_cm: Optional[float]) -> Optional[float]:
    """BMI = kg / (m)^2; None when height is missing or non-positive."""
    if height_cm is None or height_cm <= 0:
        return None
    meters = height_cm / 100.0
    return weight_kg / (meters * meters)


def weight_display(weight_kg: float, height_cm: Optional[float]) -> WeightDisplay:
    """Build the typed display view: kg, lb, stone, remaining lb, BMI."""
    whole, remaining = kg_to_stone(weight_kg)
    return WeightDisplay(
        weight_kg=weight_kg,
        lb=kg_to_lb(weight_kg),
        stone=whole,
        stone_lb=remaining,
        bmi=calculate_bmi(weight_kg, height_cm),
    )


# ---- BMI target resolution (bmi-goal-setting) -----------------------------


def weight_kg_from_bmi(
    bmi: Optional[float], height_cm: Optional[float]
) -> Optional[float]:
    """Target kg for a BMI at a height: round(bmi*(h/100)**2, 1); None when
    either input is unset."""
    if bmi is None or height_cm is None:
        return None
    meters = height_cm / 100.0
    return round(bmi * meters * meters, 1)


def healthy_weight_range(
    height_cm: Optional[float],
) -> Optional[tuple[float, float]]:
    """Healthy BMI band (18.5-24.9) expressed in kg; None when height is
    unset."""
    if height_cm is None:
        return None
    meters = height_cm / 100.0
    return (
        round(18.5 * meters * meters, 1),
        round(24.9 * meters * meters, 1),
    )


def classify_bmi(bmi: float) -> str:
    """BMI bucket: underweight (<18.5), healthy (18.5-24.9), overweight (>=25)."""
    if bmi < 18.5:
        return "underweight"
    if bmi <= 24.9:
        return "healthy"
    return "overweight"


def resolve_target_kg(
    target_weight: Optional[float],
    target_bmi: Optional[float],
    height_cm: Optional[float],
) -> Optional[float]:
    """The active target kg shared by rewards and summary: target_weight wins;
    otherwise the BMI-derived target (None when either BMI input is unset)."""
    if target_weight is not None:
        return target_weight
    return weight_kg_from_bmi(target_bmi, height_cm)
