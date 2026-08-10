# Mood Logging Specification

## Purpose

Record multiple timestamped mood check-ins per user and day.

## Requirements

### Requirement: Mood Entry Contract

The system MUST persist a `mood_entries` table whose rows carry the owner id; the API MUST represent each row to its owner as an entry-style `MoodEntry` record with id, date, time, integer mood from 1 through 5, and an optional note of at most 500 characters (the owner id lives in the persistence/API layer and is never carried on the entry dataclass, matching `WeightEntry`/`ExerciseEntry`/`MealEntry`). Multiple records for the same user and date MUST be allowed.

#### Scenario: Multiple moods in one day

- GIVEN a user has no mood records today
- WHEN moods 2 and 4 are posted at different times
- THEN both records MUST persist independently for today

#### Scenario: Validate mood and note

- GIVEN mood is outside 1–5 or note exceeds 500 characters
- WHEN the entry is posted
- THEN the API MUST return 422 and persist nothing

### Requirement: Mood API

Authenticated `POST /api/mood` MUST create an entry, `GET /api/mood` MUST list the user's entries with date and time, and `DELETE /api/mood/{entry_id}` MUST delete only an owned entry. Lists MUST use a deterministic newest-first order.

#### Scenario: Create, list, and delete

- GIVEN a valid mood payload
- WHEN it is posted, listed, and then deleted by its owner
- THEN it MUST appear once before deletion and not appear afterward

#### Scenario: Protect user isolation

- GIVEN a mood entry belongs to user B
- WHEN user A lists moods or deletes that identifier
- THEN listing MUST omit it and deletion MUST return 404 without mutation
