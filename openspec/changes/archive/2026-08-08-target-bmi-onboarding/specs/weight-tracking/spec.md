# Delta for weight-tracking

## MODIFIED Requirements

### Requirement: Settings Contract

The settings API and UI MUST support nullable `height_cm` and MUST reject non-positive supplied heights. They MUST also support nullable `target_bmi` (bounds (10, 40], `extra="forbid"` rejected) and a boolean `onboarding_complete` flag, plus the existing unit preferences (`weight_unit`, `height_unit`, `target_unit`, `weight_display`) and schedule preferences (`tip_time`, `reminder_time`, `reminder_weekday`, `exercise_time`). They MUST NOT expose, accept, or use the retired `milestone_step_kg` setting.

(Previously: contract covered only nullable `height_cm` and the retired `milestone_step_kg` rejection.)

#### Scenario: Save height

- GIVEN valid settings with no height
- WHEN a positive `height_cm` is saved
- THEN subsequent settings and weight responses MUST use that height

#### Scenario: Submit retired setting

- GIVEN current valid settings
- WHEN an update supplies `milestone_step_kg`
- THEN the update MUST be rejected and current settings MUST remain unchanged

#### Scenario: Persist target_bmi and onboarding_complete

- GIVEN valid settings with height set
- WHEN an update saves target_bmi 22 and onboarding_complete true
- THEN both MUST round-trip through GET /api/settings and current settings MUST remain otherwise unchanged

## ADDED Requirements

### Requirement: Weight Summary Contract

`GET /api/weight` MUST return a `summary` object. For each of `baseline`, `current`, `lost`, `target`, `remaining` it MUST include `*_kg`, `*_lb`, `*_stone`, and `*_stone_lb`; for `baseline`, `current`, and `target` it MUST also include `*_bmi`. The summary MUST additionally include `healthy_min_kg`, `healthy_max_kg`, and `target_status`. `healthy_min_kg`/`healthy_max_kg` MUST equal the healthy weight range and MUST be `null` when `height_cm` is unset. `target_status` MUST classify the resolved target's BMI and MUST be `null` when the target is unset or `height_cm` is unset. Target MUST be resolved through the shared `weight_kg_from_bmi` helper with `target_weight` precedence.

#### Scenario: Full summary with height and target

- GIVEN height_cm 175, height-derived healthy range (56.7, 76.3) kg, and a resolved target 70 kg
- WHEN GET /api/weight is called
- THEN summary MUST include healthy_min_kg 56.7, healthy_max_kg 76.3, and a non-null target_status

#### Scenario: Height unset nulls healthy range

- GIVEN height_cm is unset and a target is persisted
- WHEN GET /api/weight is called
- THEN healthy_min_kg and healthy_max_kg MUST be null, and target_status MUST be null

#### Scenario: Target unset nulls target_status

- GIVEN height_cm is set and no target is persisted
- WHEN GET /api/weight is called
- THEN healthy_min_kg/healthy_max_kg MUST be non-null and target_status MUST be null

#### Scenario: Summary and rewards target agree

- GIVEN settings with target_bmi 22, height 175, and entries giving start 100 kg
- WHEN GET /api/weight and GET /api/rewards are both called
- THEN summary target_kg and rewards target_kg MUST be identical