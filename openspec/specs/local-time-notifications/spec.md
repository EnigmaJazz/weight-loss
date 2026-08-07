# Local Time Notifications Specification

## Purpose

Define host-local persistence, scheduling, and calendar-day deduplication for the localhost-first single-user tracker.

## Requirements

### Requirement: Local Persisted Time

New `weight_entries.created_at`, active reward `earned_at`, and scheduled-notification `sent_at` values MUST use the host's local wall-clock time at the event. A `notifications_sent` day key MUST use the host-local calendar date on which the scheduled attempt occurs.

#### Scenario: Persist local event times

- GIVEN the host local date differs from UTC
- WHEN a weight, reward, or scheduled-send row is created
- THEN its timestamp MUST represent host-local date and time

#### Scenario: Re-earned reward timestamp

- GIVEN a revoked checkpoint is earned again
- WHEN its active reward row is recreated
- THEN `earned_at` MUST be the new host-local earning time

### Requirement: Local Scheduler Semantics

The scheduler MUST interpret each enabled `HH:MM` setting in host local time. A type MUST become due once local time is at or after its configured time and no dedupe key exists for that local date and type; a schedule persisted as `""` MUST disable that type.

#### Scenario: Scheduled type becomes due

- GIVEN a type is scheduled for `09:00` with no key for today
- WHEN a scheduler check occurs at or after 09:00 local time
- THEN the type MUST be attempted once and recorded for today

#### Scenario: API-disabled schedule is skipped

- GIVEN a notification type was persisted as `""` through `PUT /api/settings`
- WHEN the scheduler checks that type at or after its former due time
- THEN no send MUST be attempted
- AND no dedupe key MUST be written for that type and date

### Requirement: Calendar-Day Deduplication

Scheduled dedupe MUST be keyed by `(user, local calendar date, notification type)`. A successful scheduled attempt for a user with at least one subscription MUST consume that user's key. A user with zero subscriptions MUST NOT consume a key, so a later check MAY send after subscription. Manual and test notifications MUST NOT read or write scheduled dedupe keys.

#### Scenario: Repeated DST hour

- GIVEN a user's local date contains a repeated wall-clock hour
- WHEN the scheduler checks a due type multiple times in either occurrence
- THEN at most one successful scheduled attempt MUST occur for that user, date, and type

#### Scenario: Skipped DST time

- GIVEN a configured wall-clock time is skipped by a forward DST transition
- WHEN the next scheduler check occurs later on that local date
- THEN the type MUST be due for each user without a corresponding key

#### Scenario: Next local day

- GIVEN yesterday's key exists for a user and type
- WHEN that type becomes due after local midnight
- THEN a new attempt MUST be allowed under today's user-scoped key

#### Scenario: No subscriptions yet

- GIVEN a user's notification type is due and that user has zero subscriptions
- WHEN the scheduler checks the type
- THEN no dedupe key MUST be written for that user, date, and type

### Requirement: Conditional Release Polish

If the full authored-change forecast is at most 400 added-plus-deleted lines, the release MUST include manifest icons and a UI action that unsubscribes only the current browser's local push subscription. If the forecast exceeds 400 lines, both polish items MUST be deferred from this change.

#### Scenario: Forecast meets gate

- GIVEN the complete forecast is 400 changed lines or fewer
- WHEN release scope is finalized
- THEN manifest icons and local unsubscribe MUST be included

#### Scenario: Forecast exceeds gate

- GIVEN the complete forecast exceeds 400 changed lines
- WHEN release scope is finalized
- THEN both polish items MUST be excluded and recorded as deferred

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

### Requirement: Authenticated Notification Isolation

Notification settings, push subscriptions, manual sends, test sends, and scheduled dedupe state MUST be scoped to the authenticated user. Notification mutation and send endpoints MUST return status 401 without a valid session. A user MUST NOT list, remove, send to, or otherwise affect another user's subscriptions.

#### Scenario: Keep subscriptions isolated

- GIVEN users A and B have different subscriptions
- WHEN user A triggers a test or manual notification
- THEN the send MUST target only user A's subscriptions

#### Scenario: Reject unauthenticated subscription mutation

- GIVEN no valid session
- WHEN a push subscribe or unsubscribe request is made
- THEN the API MUST respond with status 401 and preserve all subscriptions

### Requirement: Per-User Scheduler Processing

Each scheduler check MUST independently process every registered user using that user's schedule settings, dedupe keys, and subscriptions. A disabled schedule for one user MUST NOT disable another user's schedule, and one user's send or dedupe key MUST NOT suppress another user's due notification.

#### Scenario: Send due notifications per user

- GIVEN two users have the same notification type due with subscriptions
- WHEN the scheduler checks that local date and time
- THEN each user MUST receive a send against only their own subscriptions
- AND each user MUST receive an independent dedupe key

#### Scenario: Skip one user's disabled schedule

- GIVEN user A disabled a type and user B has that type due
- WHEN the scheduler checks both users
- THEN user A MUST be skipped and user B MUST still be processed

## Acceptance Criteria

- Tests MUST cover local-date timestamps, due checks, per-type day dedupe, and DST repeat/skip cases.
- The full pytest suite and Pyright MUST pass, and the repository MUST receive an initial conventional commit.
