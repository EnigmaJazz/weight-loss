# Weight Tracking Specification

## Purpose

Define kg-canonical weight records and deterministic kg, lb, stone, and BMI presentation for the single-user tracker.

## Requirements

### Requirement: Canonical Weight Mutations

The system MUST store one positive `weight_kg` value per date. An upsert MUST create a missing date or replace that date's kg value, and a delete MUST remove the addressed entry and recompute dependent summaries from the remaining entries.

#### Scenario: Create and update one date

- GIVEN no entry exists for a valid date
- WHEN 80 kg is upserted and then 79 kg is upserted for that date
- THEN exactly one entry MUST remain with canonical value 79 kg

#### Scenario: Delete an entry

- GIVEN an entry contributes to history and the current summary
- WHEN that entry is deleted
- THEN it MUST disappear and history and summary MUST reflect only remaining entries

### Requirement: Multi-Unit Presentation

The system MUST render each summary, history, and chart-tooltip weight as `kg (lb; st lb)`, derived only from canonical kg. Total lb MUST equal `kg × 2.2046226218`; whole stone MUST equal `floor(total lb ÷ 14)` and remaining lb MUST equal `total lb − 14 × whole stone`. Rounding MUST be presentation-only and consistent across views.

#### Scenario: Derive alternate units

- GIVEN a canonical entry of 70 kg
- WHEN any weight view is rendered
- THEN lb and stone values MUST be derived from 70 kg using the specified formulas

#### Scenario: Update canonical kg

- GIVEN displayed alternate units for an entry
- WHEN its canonical kg value is upserted
- THEN every derived display MUST change without storing alternate-unit values

### Requirement: BMI Presentation

Settings MAY contain a positive `height_cm`. When present, the system MUST calculate BMI for a weight as `weight_kg ÷ (height_cm ÷ 100)²` and MUST show it in the current summary, each history row, and each chart tooltip. Calculation MUST use unrounded kg and height values.

#### Scenario: Height is configured

- GIVEN `height_cm` is 175 and a weight is 70 kg
- WHEN BMI is presented for that weight
- THEN the calculated BMI MUST be 22.857142... before presentation rounding

#### Scenario: Height is absent

- GIVEN `height_cm` is unset
- WHEN summary, history, or chart BMI is rendered
- THEN each BMI display MUST be `—`

### Requirement: Settings Contract

The settings API and UI MUST support nullable `height_cm` and MUST reject non-positive supplied heights. They MUST NOT expose, accept, or use the retired `milestone_step_kg` setting.

#### Scenario: Save height

- GIVEN valid settings with no height
- WHEN a positive `height_cm` is saved
- THEN subsequent settings and weight responses MUST use that height

#### Scenario: Submit retired setting

- GIVEN current valid settings
- WHEN an update supplies `milestone_step_kg`
- THEN the update MUST be rejected and current settings MUST remain unchanged

## Acceptance Criteria

- Automated tests MUST cover upsert, delete, conversions, configured-height BMI, and no-height BMI.
- The API and UI MUST present canonical kg plus derived lb, stone, and BMI consistently.
