# Delta for User Onboarding

## ADDED Requirements

### Requirement: Goals and Lifestyle Settings

Settings and `AppSettings` MUST support optional `primary_goal`, `secondary_goals`, `health_domains`, and `activity_level`. Missing values MUST default to `null`, `[]`, `[]`, and `null`; list fields MUST round-trip as JSON lists. Primary goal MUST be one of `weight_loss|general_health|fitness|wellbeing`; activity level MUST be one of `sedentary|light|moderate|active`. The Me tab MUST provide a goals/lifestyle settings card.

#### Scenario: Optional fields round-trip per user

- GIVEN users A and B save different valid goals and lifestyle values
- WHEN each reads settings
- THEN each MUST receive only their own values with list order preserved

#### Scenario: Reject invalid allowlist values

- GIVEN onboarding or settings contains an out-of-allowlist primary goal or activity level
- WHEN submitted
- THEN the API MUST return 422 and preserve current settings

## MODIFIED Requirements

### Requirement: Onboarding Request Contract

`POST /api/onboarding` MUST accept `OnboardingIn` with `extra="forbid"`: required positive `height_cm` and `weight_kg`; exactly one of `target_weight` XOR `target_bmi`; existing optional preferences; and the four optional goals/lifestyle fields with the stated allowlists and JSON-list shapes. Validation MUST check height before BMI target bounds.

(Previously: Onboarding accepted health measurements, target, units, and schedules but no goals/lifestyle fields.)

#### Scenario: Valid weight-target payload

- GIVEN an authenticated user needs onboarding and supplies required values plus valid optional goals
- WHEN POST /api/onboarding is called
- THEN the request MUST be accepted

#### Scenario: Reject XOR violation

- GIVEN a payload supplies both or neither target forms
- WHEN POST /api/onboarding is called
- THEN the API MUST respond 422 and persist nothing

#### Scenario: Height checked before BMI bounds

- GIVEN target_bmi is supplied but height is unset or non-positive
- WHEN POST /api/onboarding is called
- THEN the API MUST respond 422 for height before evaluating BMI bounds

#### Scenario: Reject unknown key

- GIVEN the payload includes an unknown key
- WHEN POST /api/onboarding is called
- THEN the API MUST respond 422 and persist nothing

### Requirement: Atomic Idempotent Completion

`complete_onboarding` MUST atomically upsert all supplied settings including goals/lifestyle, insert today's weight, and reconcile rewards. A second valid request MUST not duplicate today's weight and MUST overwrite settings.

(Previously: Atomic completion covered measurements, targets, and preferences only.)

#### Scenario: Happy atomic completion

- GIVEN an authenticated user needs onboarding and submits valid optional goals
- WHEN onboarding completes
- THEN all supplied settings and onboarding_complete true MUST persist
- AND exactly one weight entry MUST exist for today

#### Scenario: Idempotent re-POST

- GIVEN onboarding already completed today
- WHEN a valid payload is posted again
- THEN today's weight MUST remain single and settings MUST be overwritten

#### Scenario: Partial failure rolls back

- GIVEN the weight insert fails mid-transaction
- WHEN completion runs
- THEN NO setting, weight, or reward change MUST persist

### Requirement: Wizard SPA Gate

The SPA MUST branch on `needs_onboarding` before tracker loading. The wizard MUST have six ordered steps: height, weight, target, `goals-lifestyle`, units, notifications, with `#wizard-step-goals-lifestyle` between target and units. `test_index_html_ships_onboarding_wizard_between_auth_and_tracker`, `test_index_html_ships_mascot_and_wizard_indicator`, and the smoke wizard flow MUST be updated in this slice.

(Previously: The wizard had five steps and no Goals & lifestyle step.)

#### Scenario: Show six-step wizard for flagged user

- GIVEN `needs_onboarding` is true
- WHEN the SPA boots
- THEN tracker data MUST stay hidden and the six steps MUST appear in the specified order

#### Scenario: Skip wizard for completed user

- GIVEN `needs_onboarding` is false
- WHEN the SPA boots
- THEN the tracker MUST load without showing the wizard
