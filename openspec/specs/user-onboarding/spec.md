# User Onboarding Specification

## Purpose

Gate first-time users behind a one-time wizard that atomically collects height, first weight, target, and preferences, exposing a `needs_onboarding` flag to the SPA.

## Requirements

### Requirement: needs_onboarding Flag

The `onboarding_complete` settings flag MUST default absent. A user with no `onboarding_complete` row MUST be reported `needs_onboarding: true`; setting it to true MUST flip the flag to false.

#### Scenario: New account needs onboarding

- GIVEN an account with no onboarding_complete row
- WHEN /api/auth/me is requested
- THEN needs_onboarding MUST be true

#### Scenario: Completed onboarding

- GIVEN onboarding_complete is true
- WHEN /api/auth/me is requested
- THEN needs_onboarding MUST be false

#### Scenario: Pre-existing accounts flagged once

- GIVEN accounts created before this change have no onboarding_complete row
- WHEN they next authenticate
- THEN needs_onboarding MUST be true, surfacing the wizard once

### Requirement: Onboarding Request Contract

`POST /api/onboarding` MUST accept `OnboardingIn` with `extra="forbid"`: `height_cm` (required, positive), `weight_kg` (required, positive, today's first entry), exactly one of `target_weight` XOR `target_bmi`, and optional unit and schedule preferences reusing existing settings shapes. Validation MUST check height presence before BMI target bounds.

#### Scenario: Valid weight-target payload

- GIVEN an authenticated user needs onboarding and height_cm 175, weight_kg 80, target_weight 70
- WHEN POST /api/onboarding is called
- THEN the request MUST be accepted

#### Scenario: Reject XOR violation

- GIVEN a payload supplies both or neither of target_weight and target_bmi
- WHEN POST /api/onboarding is called
- THEN the API MUST respond 422 and persist nothing

#### Scenario: Height checked before BMI bounds

- GIVEN a payload with target_bmi but height_cm unset or non-positive
- WHEN POST /api/onboarding is called
- THEN the API MUST respond 422 for height without evaluating target_bmi bounds

#### Scenario: Reject unknown key

- GIVEN the payload includes an unknown key
- WHEN POST /api/onboarding is called
- THEN the API MUST respond 422 and persist nothing

### Requirement: Atomic Idempotent Completion

`complete_onboarding` MUST upsert settings, insert today's weight entry, and reconcile active rewards in a single transaction. A second valid `POST /api/onboarding` by the same user MUST be idempotent: today's weight MUST NOT duplicate and settings MUST be overwritten, not appended.

#### Scenario: Happy atomic completion

- GIVEN an authenticated user needs onboarding and a valid payload
- WHEN POST /api/onboarding is called
- THEN settings MUST contain height, target, prefs, and onboarding_complete true
- AND exactly one weight entry MUST exist for today and rewards MUST be reconciled

#### Scenario: Idempotent re-POST

- GIVEN onboarding already completed today
- WHEN the same payload is POSTed again
- THEN today's weight MUST remain a single entry and settings MUST be overwritten

#### Scenario: Partial failure rolls back

- GIVEN the weight insert would violate a constraint mid-transaction
- WHEN complete_onboarding runs
- THEN NO settings, weight, or reward change MUST persist

### Requirement: Onboarding Authorization

`POST /api/onboarding` MUST require an authenticated session; unauthenticated requests MUST return 401, and a user MUST NOT onboard on behalf of another user.

#### Scenario: Reject unauthenticated

- GIVEN no valid session
- WHEN /api/onboarding is POSTed
- THEN the API MUST respond 401 and persist nothing

### Requirement: Wizard SPA Gate

The SPA MUST branch on `needs_onboarding` from `/api/auth/me` and show the onboarding wizard once for flagged users before any tracker data loads.

#### Scenario: Show wizard for flagged user

- GIVEN /api/auth/me returns needs_onboarding true
- WHEN the SPA boots
- THEN the onboarding screen MUST render and tracker data MUST stay hidden until completion

#### Scenario: Skip wizard for completed user

- GIVEN /api/auth/me returns needs_onboarding false
- WHEN the SPA boots
- THEN the tracker MUST load without showing the wizard

## Acceptance Criteria

- Tests MUST cover needs_onboarding for new and pre-existing accounts, XOR/height validation order, atomic completion, idempotent re-POST, and 401/422 rejections.