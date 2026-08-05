# Delta for Local Time Notifications

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Calendar-Day Deduplication

Scheduled dedupe MUST be keyed by `(user, local calendar date, notification type)`. A successful scheduled attempt for a user with at least one subscription MUST consume that user's key. A user with zero subscriptions MUST NOT consume a key, so a later check MAY send after subscription. Manual and test notifications MUST NOT read or write scheduled dedupe keys.

(Previously: Dedupe was global by date and type, and an attempt with zero subscriptions consumed the key.)

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
