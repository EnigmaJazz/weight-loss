# Achievements Specification

## Purpose

Define six behaviour milestones.

## Requirements

### Requirement: Achievement Catalogue and State

The catalogue MUST contain these ordered entries:

| Key | Title |
|---|---|
| `getting_started` | Getting Started |
| `moving_forward` | Moving Forward |
| `consistency` | Consistency |
| `comeback` | Comeback |
| `explorer` | Explorer |
| `personal_best` | Personal Best |

Each state MUST expose `key`, `title`, `earned`, and `unlocked_at`. The date MUST be the earliest qualifying ISO local date when earned and `null` when locked.

#### Scenario: Empty history

- GIVEN no qualifying history
- WHEN state is derived
- THEN all six MUST appear in order, locked with null dates

### Requirement: Quest-Completion Achievements

Getting Started MUST earn on the first done quest. Moving Forward MUST earn on the tenth done quest with `quest_key == 'exercise_10'`; nothing else MUST count. Explorer MUST earn at five distinct persisted domains among done quests. Dates MUST use `quest.date`, not `completed_at`.

#### Scenario: Quest thresholds and dates

- GIVEN history crosses all three thresholds
- WHEN state is derived
- THEN dates MUST identify the first quest, tenth qualifier, and fifth first-seen domain

#### Scenario: Moving Forward key boundary

- GIVEN done `streak_alive` quests and nine done `exercise_10` quests
- WHEN state is derived
- THEN Moving Forward MUST remain locked

### Requirement: Momentum Achievements

Consistency MUST earn when any seven consecutive local dates contain five `is_successful` days; its date MUST be the fifth success in the earliest qualifying span. Comeback MUST earn on the earliest action date immediately after three consecutive inactive dates. A return MUST have `action_count >= 1`. Inactivity MUST have `assigned_quests > 0` and zero actions; skipped counts as assigned, while replaced-only dates break the run.

#### Scenario: Any-window qualification

- GIVEN five Good or Great days occur within any seven historical dates
- WHEN state is derived
- THEN Consistency MUST earn on the fifth successful date

#### Scenario: Spark is not successful

- GIVEN a span contains four successful days and one Spark day
- WHEN state is derived
- THEN Consistency MUST remain locked

#### Scenario: Spark return after inactivity

- GIVEN three consecutive inactive dates
- WHEN the next date has one action
- THEN Comeback MUST earn on the return date

#### Scenario: Neutral date breaks the run

- GIVEN inactivity is interrupted by a replaced-only date
- WHEN an action later occurs without a new three-date run
- THEN Comeback MUST remain locked

### Requirement: Personal Best Achievement

Daily activity MUST equal that user's summed exercise minutes. Personal Best MUST earn on the earliest date whose sum exceeds every earlier daily sum, using zero for empty pre-history. The first positive date MUST qualify. State MAY lock again if edits or deletions remove all qualifying evidence.

#### Scenario: First positive exercise day

- GIVEN no earlier duration and a positive daily sum
- WHEN state is derived
- THEN Personal Best MUST earn on that date

#### Scenario: Per-user daily sums

- GIVEN two users have exercise rows
- WHEN one user's state is derived
- THEN only that user's per-date sums MUST count

### Requirement: Achievements API and Read-Diff Contract

`GET /api/achievements` MUST require authentication and return only the current user's six states. The client MUST diff earned-key sets after successful reads, suppress the first read, and celebrate only new keys. Unchanged or disappearing keys MUST NOT celebrate. Server push and partial progress MUST NOT be exposed.

#### Scenario: Isolated API response

- GIVEN two users have different histories
- WHEN one requests `/api/achievements`
- THEN only that user's state MUST appear; unauthenticated requests MUST return 401

#### Scenario: First render and later unlock

- GIVEN no prior successful read
- WHEN a set first loads and later gains one key
- THEN the first read MUST be quiet and the later diff MUST identify that key once
