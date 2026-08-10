# XP Progression Specification

## Purpose

Derive per-user XP, levels, and titles solely from completed quests.

## Requirements

### Requirement: Derived XP

Total XP MUST equal the per-user sum of `xp_value` for quests whose status is `done`. Open, skipped, and replaced quests MUST contribute zero; XP MUST NOT use a mutable ledger or `reward_events`.

#### Scenario: Sum completed quests only

- GIVEN a user has done quests worth 20 and 40 plus skipped and replaced quests worth 40
- WHEN XP is calculated
- THEN total XP MUST be 60

#### Scenario: Keep users isolated

- GIVEN users A and B have different completed quests
- WHEN user A requests XP
- THEN only user A's done quests MUST contribute

### Requirement: Exact Level Curve

Level 1 MUST start at 0 XP. Advancing from level `n` MUST cost `100 + (n-1)×50` XP, so level `L` starts at `T(L)=25(L-1)(L+2)`. Level from XP MUST be the greatest `L≥1` whose threshold is not above total XP, equivalently `floor((sqrt(9+4×XP/25)-1)/2)` clamped to at least 1.

#### Scenario: Boundary vectors

- GIVEN totals of 99, 100, and 250 XP
- WHEN levels are calculated
- THEN they MUST resolve to levels 1, 2, and 3 respectively

#### Scenario: Progress within a level

- GIVEN total XP is between `T(L)` and `T(L+1)`
- WHEN progress is calculated
- THEN `xp_into_next` MUST equal `total-T(L)` and `next_level_at` MUST equal `T(L+1)`

### Requirement: Level Titles

`LEVEL_TITLES` MUST map levels 1–4 to `Sprout`, 5–9 to `Explorer`, 10–19 to `Adventurer`, 20–29 to `Champion`, and 30+ to `Legend`.

#### Scenario: Title band boundary

- GIVEN levels 4, 5, 29, and 30
- WHEN titles are resolved
- THEN they MUST be `Sprout`, `Explorer`, `Champion`, and `Legend`

### Requirement: XP API and Level-Up Diff

Authenticated `GET /api/xp` MUST return `level`, `title`, `total_xp`, `xp_into_next`, and `next_level_at`. A quest-completion result MUST detect level-up by comparing level from XP immediately before and after the idempotent status transition; reads and repeated completion MUST NOT emit a new level-up.

#### Scenario: Completion crosses a boundary

- GIVEN a user has 80 XP and completes a 20-XP open quest
- WHEN before and after levels are compared
- THEN the result MUST report a change from level 1 to level 2

#### Scenario: Repeated completion is quiet

- GIVEN that quest is already done
- WHEN completion is posted again
- THEN XP MUST remain unchanged and no level-up MUST be reported
