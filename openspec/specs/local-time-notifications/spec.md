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

The scheduler MUST interpret each enabled `HH:MM` setting in host local time. A type MUST become due once local time is at or after its configured time and no dedupe key exists for that local date and type; an empty schedule MUST disable that type.

#### Scenario: Scheduled type becomes due

- GIVEN a type is scheduled for `09:00` with no key for today
- WHEN a scheduler check occurs at or after 09:00 local time
- THEN the type MUST be attempted once and recorded for today

#### Scenario: Schedule is disabled

- GIVEN a notification type has an empty schedule
- WHEN the scheduler checks that type
- THEN no send MUST be attempted and no day key MUST be written

### Requirement: Calendar-Day Deduplication

Scheduled dedupe MUST be keyed by `(local calendar date, notification type)`. A scheduled attempt, including one with zero subscriptions, MUST consume that key; manual and test notifications MUST NOT read or write scheduled dedupe keys.

#### Scenario: Repeated DST hour

- GIVEN a local date contains a repeated wall-clock hour
- WHEN the scheduler checks a due type multiple times in either occurrence
- THEN at most one scheduled attempt MUST occur for that date and type

#### Scenario: Skipped DST time

- GIVEN a configured wall-clock time is skipped by a forward DST transition
- WHEN the next scheduler check occurs later on that local date
- THEN the type MUST be due if no key exists

#### Scenario: Next local day

- GIVEN yesterday's key exists for a type
- WHEN that type becomes due after local midnight
- THEN a new attempt MUST be allowed under today's key

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

## Acceptance Criteria

- Tests MUST cover local-date timestamps, due checks, per-type day dedupe, and DST repeat/skip cases.
- The full pytest suite and Pyright MUST pass, and the repository MUST receive an initial conventional commit.
