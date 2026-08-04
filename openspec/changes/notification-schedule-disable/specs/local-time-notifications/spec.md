# Delta for Local Time Notifications

## ADDED Requirements

### Requirement: Notification Schedule Settings API

`PUT /api/settings` notification time fields (`tip_time`, `reminder_time`, and `exercise_time`) MUST accept strict `HH:MM`, `""`, or `null` values. An empty string MUST persist as the disabled sentinel and round-trip unchanged through `GET /api/settings`; `null` MUST remove the override and restore the configured default. Any other non-empty value MUST be rejected with status 422.

#### Scenario: Disable a notification schedule

- GIVEN any notification time field has an enabled value
- WHEN the client updates that field to `""`
- THEN the update MUST succeed and persist `""`
- AND `GET /api/settings` MUST return `""` for that field

#### Scenario: Restore a notification default

- GIVEN a notification time field has an override
- WHEN the client updates that field to `null`
- THEN the override MUST be removed
- AND the configured default MUST be returned for that field

#### Scenario: Reject an invalid non-empty schedule

- GIVEN a notification time value is neither strict `HH:MM`, `""`, nor `null`
- WHEN the client submits it to `PUT /api/settings`
- THEN the API MUST respond with status 422
- AND the existing setting MUST remain unchanged

### Requirement: Notification Schedule Settings Form

The SPA settings form MUST preserve the distinction between disabling and restoring a default. Clearing a notification time input MUST submit `""`, not `null`, and a returned `""` MUST be displayed as an empty input.

#### Scenario: Clear a schedule in the form

- GIVEN a notification time input contains a value
- WHEN the user clears the input and saves the form
- THEN the SPA MUST submit `""` for that field
- AND it MUST NOT submit `null` for that field

#### Scenario: Display a disabled schedule

- GIVEN `GET /api/settings` returns `""` for a notification time field
- WHEN the SPA renders the settings form
- THEN the corresponding input MUST display an empty value

## MODIFIED Requirements

### Requirement: Local Scheduler Semantics

The scheduler MUST interpret each enabled `HH:MM` setting in host local time. A type MUST become due once local time is at or after its configured time and no dedupe key exists for that local date and type; a schedule persisted as `""` MUST disable that type.

(Previously: The scheduler disabled an empty schedule without explicitly tying that value to the persisted settings contract.)

#### Scenario: Scheduled type becomes due

- GIVEN a type is scheduled for `09:00` with no key for today
- WHEN a scheduler check occurs at or after 09:00 local time
- THEN the type MUST be attempted once and recorded for today

#### Scenario: API-disabled schedule is skipped

- GIVEN a notification type was persisted as `""` through `PUT /api/settings`
- WHEN the scheduler checks that type at or after its former due time
- THEN no send MUST be attempted
- AND no dedupe key MUST be written for that type and date
