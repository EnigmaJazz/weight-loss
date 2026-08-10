# Daily Quests Specification

## Purpose

Provide each authenticated user with three deterministic daily health quests whose completion can be explicit or detected from honest logging.

## Requirements

### Requirement: Quest Catalogue and Persistence

The system MUST persist a per-user `quests` table represented by a `Quest` dataclass with id, date, key, domain, XP value, status, completion source, and timestamps. Status MUST be one of `open`, `done`, `skipped`, or `replaced`. The v1 catalogue MUST be:

| Key | Domain | Size / XP | Detection |
|---|---|---|---|
| `log_weight` | weight | small / 20 | weight row |
| `mood_checkin` | wellbeing | small / 20 | mood row |
| `exercise_10` | exercise | normal / 40 | exercise row |
| `log_meal` | nutrition | small / 20 | meal row |
| `streak_alive` | movement | small / 20 | any qualifying entry row |
| `habit_checkin` | routine | small / 20 | habit row |

#### Scenario: Persist a user's daily assignment

- GIVEN a user has no quests for a date
- WHEN that date's quests are generated
- THEN exactly three records MUST persist with catalogue domain and XP values
- AND another user MAY have independent records for the same date and keys

### Requirement: Deterministic Daily Generation

`mood_checkin` MUST always be assigned. `log_weight` MUST be assigned only when the date's weekday equals the user's resolved `reminder_weekday`. A weigh-in day MUST add one rotating key; every other day MUST add two. Rotation MUST use a stable hash of `(user_id, date)` and MUST not change across reads that day.

#### Scenario: Weigh-in weekday

- GIVEN the date matches `reminder_weekday`
- WHEN quests are first read
- THEN the set MUST be `log_weight`, `mood_checkin`, and one rotating key

#### Scenario: Other weekday is deterministic

- GIVEN the date does not match `reminder_weekday`
- WHEN quests are read repeatedly with the same hash seed
- THEN `log_weight` MUST be absent and the same two rotating keys MUST accompany `mood_checkin`

### Requirement: Lifecycle, Skip, and Replace

Completing an open quest MUST make it `done` and MUST be idempotent. Skipping MUST be terminal and award no XP. Replacing MUST mark the original `replaced`, create one eligible open replacement, exclude every key assigned or previously used as a replacement that day, and be limited to one replacement per user per day.

#### Scenario: Idempotent completion and skip

- GIVEN one open quest and one skipped quest
- WHEN completion is posted twice for the open quest and once for the skipped quest
- THEN the first MUST remain done once and the skipped quest MUST remain skipped with zero XP

#### Scenario: Replacement cap and exclusions

- GIVEN a user has not replaced a quest today
- WHEN replacement is requested twice
- THEN the first MUST use an unassigned eligible key and the second MUST return 409 without mutation

### Requirement: Read-Detected Completion and API Isolation

`GET /api/quests` MUST generate today's assignment when absent, reconcile it, and return quest id, date, key, domain, XP, status, and completion source plus bounded recent history. An existing same-date weight, exercise, meal, mood, or habit row MUST mark its mapped open quest `done` with source `detected`; mood/habit detection MUST remain inactive until their tables exist. Existing log routes MUST NOT write quest state. `POST /api/quests/{id}/complete|skip|replace` MUST be authenticated and ownership-scoped.

#### Scenario: Entry predates quest render

- GIVEN a qualifying entry exists before today's quests are rendered
- WHEN `GET /api/quests` reconciles the date
- THEN the matching quest MUST be returned done with completion source `detected`

#### Scenario: Foreign quest is hidden

- GIVEN a quest belongs to user B
- WHEN user A addresses its identifier on any quest mutation endpoint
- THEN the API MUST return 404 and preserve user B's quest
