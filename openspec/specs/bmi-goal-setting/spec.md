# BMI Goal Setting Specification

## Purpose

Define BMI-based target goal resolution, healthy-weight range recommendation, and BMI classification, expressed in kg so rewards and summary share one resolved target.

## Requirements

### Requirement: Shared Target Resolution

The system MUST resolve the active target through one shared pure helper used by both rewards and summary so they cannot disagree. `weight_kg_from_bmi(target_bmi, height_cm)` MUST return `round(target_bmi × (height_cm ÷ 100)², 1)`. When either input is unset it MUST return `None`. `target_weight` MUST take precedence over `target_bmi`.

#### Scenario: Both inputs set

- GIVEN target_bmi 22.0 and height_cm 175
- WHEN the helper resolves target kg
- THEN it MUST return 67.4 kg

#### Scenario: Either input unset

- GIVEN target_bmi is set and height_cm is unset
- WHEN the helper resolves target kg
- THEN it MUST return None

#### Scenario: Boundary conversion

- GIVEN target_bmi 18.5 and height_cm 200
- WHEN the helper resolves target kg
- THEN it MUST return exactly 74.0 kg

#### Scenario: Weight precedence

- GIVEN settings persist target_weight 80 kg AND target_bmi 22 with height 175
- WHEN the shared target resolver runs for rewards or summary
- THEN the resolved target MUST be 80 kg, never the BMI-derived value

### Requirement: BMI Classification

`classify_bmi(bmi)` MUST classify values as underweight (<18.5), healthy (18.5–24.9), or overweight (≥25. No obese bucket exists in v1.

#### Scenario: Bucket boundaries

- GIVEN BMI values exactly 18.5, 24.9, and 25.0
- WHEN classify_bmi evaluates each
- THEN 18.5 MUST be healthy, 24.9 MUST be healthy, and 25.0 MUST be overweight

#### Scenario: Below healthy

- GIVEN BMI 18.4
- WHEN classify_bmi evaluates it
- THEN it MUST classify as underweight

### Requirement: Healthy Weight Range

`healthy_weight_range(height_cm)` MUST return `(round(18.5 × (h ÷ 100)², 1), round(24.9 × (h ÷ 100)², 1))`. When height is unset it MUST return `None`.

#### Scenario: Height set

- GIVEN height_cm 175
- WHEN the healthy range is requested
- THEN it MUST return (56.7, 76.3) kg

#### Scenario: Height unset

- GIVEN height_cm is unset
- WHEN the healthy range is requested
- THEN the result MUST be None

### Requirement: target_bmi Settings Bounds

`SettingsIn` MUST accept a nullable `target_bmi` in the range (10, 40] and MUST use `extra="forbid"` so unknown keys are rejected. Out-of-range, non-numeric, or non-finite values MUST return 422. Saving a BMI target MUST clear `target_weight`; `target_kg` MUST be derived on read only and never persisted.

#### Scenario: Accept and round-trip a valid target_bmi

- GIVEN height_cm is set and target_bmi is 22
- WHEN settings are saved
- THEN target_bmi MUST round-trip through GET /api/settings and target_weight MUST be cleared

#### Scenario: Reject out-of-range

- GIVEN target_bmi is 5 or 45
- WHEN settings are saved
- THEN the API MUST respond 422 and persist no change

#### Scenario: Store target_bmi without height

- GIVEN height_cm is unset and target_bmi is 22
- WHEN settings are saved
- THEN target_bmi MUST persist, the resolved target MUST be null, and no 422 MUST be raised

## Acceptance Criteria

- Tests MUST cover (10, 40] bounds, 18.5/24.9/25.0 classification boundaries, height-unset null semantics, and target_weight precedence.