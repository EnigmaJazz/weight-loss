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
