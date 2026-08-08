# Delta for weight-tracking

## MODIFIED Requirements

### Requirement: Settings Contract

The settings API and UI MUST support nullable `height_cm` and MUST reject non-positive supplied heights. They MUST also support nullable `target_bmi` (bounds (10, 40], `extra="forbid"` rejected) and a boolean `onboarding_complete` flag, plus the existing unit preferences (`weight_unit`, `height_unit`, `target_unit`, `weight_display`), schedule preferences (`tip_time`, `reminder_time`, `reminder_weekday`, `exercise_time`), and a per-user `theme` key with value `"system"` (default), `"light"`, or `"dark"`. `SettingsIn` MUST reject any `theme` outside that set with 422 and a missing row MUST default to `"system"`. They MUST NOT expose, accept, or use the retired `milestone_step_kg` setting, and `OnboardingIn` MUST NOT accept a `theme` key.
(Previously: no `theme` key; unit, target_bmi, schedule, and onboarding_complete keys only.)

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

#### Scenario: theme round-trips and defaults

- GIVEN an authenticated user with default settings
- WHEN `PUT /api/settings` saves `theme: "dark"`, `theme: "light"`, `theme: "system"` in turn
- THEN each `GET /api/settings` MUST return the exact value saved, and a user with no theme row MUST read `system`

#### Scenario: Reject invalid theme

- GIVEN an authenticated user with valid settings
- WHEN an update supplies `theme: "purple"`
- THEN the API MUST respond 422 and current settings MUST remain unchanged

#### Scenario: Onboarding does not accept theme

- GIVEN an onboarding payload
- WHEN `POST /api/onboard` is sent with a `theme` key
- THEN the request MUST be rejected per `OnboardingIn` and theme MUST NOT be set

#### Scenario: theme is per-user isolated

- GIVEN users A and B with distinct registered accounts
- WHEN A persists `theme: "dark"` and B persists `theme: "system"`
- THEN GET /api/settings for A MUST return `dark` and for B MUST return `system`, with no cross-contamination