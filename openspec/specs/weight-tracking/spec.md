# Weight Tracking Specification

## Purpose

Define kg-canonical weight records and deterministic kg, lb, stone, and BMI presentation for the single-user tracker.

## Requirements

### Requirement: Canonical Weight Mutations

The system MUST store one positive `weight_kg` value per date for each authenticated user. An upsert MUST create or replace only that user's value for the date, and a delete MUST remove only an entry owned by that user and recompute only that user's dependent summaries. The same date MAY exist once for each user.

#### Scenario: Create and update one date

- GIVEN no entry exists for an authenticated user on a valid date
- WHEN 80 kg and then 79 kg are upserted by that user for that date
- THEN exactly one of that user's entries MUST remain with canonical value 79 kg

#### Scenario: Delete an entry

- GIVEN an owned entry contributes to the authenticated user's history and summary
- WHEN that user deletes the entry
- THEN it MUST disappear and only that user's history and summary MUST be recomputed

#### Scenario: Reject cross-user deletion

- GIVEN an entry belongs to user B
- WHEN authenticated user A deletes its identifier
- THEN the API MUST respond with status 404 and preserve the entry

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

The settings API and UI MUST support nullable `height_cm` and MUST reject non-positive supplied heights. They MUST also support nullable `target_bmi` (bounds (10, 40], `extra="forbid"` rejected) and a boolean `onboarding_complete` flag, plus the existing unit preferences (`weight_unit`, `height_unit`, `target_unit`, `weight_display`) and schedule preferences (`tip_time`, `reminder_time`, `reminder_weekday`, `exercise_time`). They MUST NOT expose, accept, or use the retired `milestone_step_kg` setting.

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

### Requirement: Authenticated Weight and Settings APIs

Every weight and settings endpoint MUST require an authenticated user. `GET /api/weight`, `POST /api/weight`, `DELETE /api/weight/{entry_id}`, `GET /api/settings`, and `PUT /api/settings` MUST read or mutate only that user's data. Unauthenticated requests MUST return status 401 without changing state.

#### Scenario: Reject unauthenticated weight access

- GIVEN no valid session
- WHEN any weight or settings endpoint is requested
- THEN the API MUST respond with status 401
- AND no weight or setting MUST be disclosed or changed

#### Scenario: Keep two users isolated

- GIVEN users A and B have different weights and settings
- WHEN user A reads weight history and settings
- THEN only user A's values MUST be returned

### Requirement: Legacy Pre-Auth Data Is Discarded on Migration

When a pre-auth database is migrated, all legacy rows MUST be discarded — no account inherits them. Every account, including the first, MUST start with an empty dataset and set its own target, height, and schedules. The discard MUST be atomic with the schema rebuild and MUST NOT run again on already-migrated databases.

#### Scenario: First account starts empty after migration

- GIVEN legacy settings and entries exist and no account exists
- WHEN the database is migrated and the first account is registered
- THEN the account MUST have no settings, entries, rewards, subscriptions, or dedupe rows

#### Scenario: Later accounts also start empty

- GIVEN a migrated database
- WHEN any account is registered
- THEN it MUST start with an empty dataset and no inherited data MUST change

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

## Acceptance Criteria

- Automated tests MUST cover upsert, delete, conversions, configured-height BMI, and no-height BMI.
- The API and UI MUST present canonical kg plus derived lb, stone, and BMI consistently.


## Extended by dark-mode (2026-08-08)

### ADDED Requirement: Theme Preference Key

The settings contract MUST support a per-user `theme` key with values "system" (default), "light", or "dark"; any other value MUST be rejected with 422. The key MUST round-trip through PUT/GET /api/settings, default to "system" when the row is absent, be per-user isolated, and MUST NOT be accepted by the onboarding payload.
