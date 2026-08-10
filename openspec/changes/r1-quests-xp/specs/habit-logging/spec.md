# Habit Logging Specification

## Purpose

Record repeatable healthy-routine check-ins from a fixed v1 catalogue.

## Requirements

### Requirement: Habit Entry Contract

The system MUST persist a `habit_entries` table whose rows carry the owner id; the API MUST represent each row to its owner as an entry-style `HabitEntry` record with id, date, time, and `habit_type` (the owner id lives in the persistence/API layer and is never carried on the entry dataclass, matching `WeightEntry`/`ExerciseEntry`/`MealEntry`). Multiple records for the same user and date MUST be allowed. `HABIT_TYPES` MUST allow exactly `water`, `fruit_veg`, `home_cooked`, and `sleep_routine`.

#### Scenario: Multiple habits in one day

- GIVEN a user has no habit records today
- WHEN `water` and `home_cooked` are posted
- THEN both records MUST persist independently for today

#### Scenario: Reject unknown habit

- GIVEN `habit_type` is not in `HABIT_TYPES`
- WHEN the entry is posted
- THEN the API MUST return 422 and persist nothing

### Requirement: Habit API and Isolation

Authenticated `POST /api/habits` MUST create an entry, `GET /api/habits` MUST list only the current user's entries with date and time in deterministic newest-first order, and `DELETE /api/habits/{entry_id}` MUST delete only an owned entry.

#### Scenario: Create, list, and delete

- GIVEN a valid habit payload
- WHEN it is posted, listed, and deleted by its owner
- THEN it MUST appear once before deletion and not appear afterward

#### Scenario: Protect another user's entry

- GIVEN a habit entry belongs to user B
- WHEN user A lists habits or deletes that identifier
- THEN listing MUST omit it and deletion MUST return 404 without mutation

### Requirement: Habit Allowlist Drift Guard

The API validator, stored catalogue, UI choices, and quest-detection mapping MUST derive from or exactly match `HABIT_TYPES`; an automated drift guard MUST pin the four-value set.

#### Scenario: Catalogue stays aligned

- GIVEN the four v1 constants
- WHEN the drift guard compares backend validation, UI options, and detection keys
- THEN every surface MUST contain exactly the same four values
