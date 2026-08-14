# Collectibles Specification

## Purpose

Define cosmetic tokens derived monotonically from retained user history and their Journey and World presentation.

## Requirements

### Requirement: R10 — Cosmetic-Only Tokens

Collectibles MUST be cosmetic and MUST NOT alter XP, goals, quest generation, progression, or any economy.

#### Scenario: A token is earned

- GIVEN a collectible source becomes true
- WHEN the token is displayed
- THEN gameplay and progression values MUST remain unchanged

### Requirement: R11 — Complete Source Catalogue

The catalogue MUST include one token for each of six achievement families, five goal checkpoints (10%, 25%, 50%, 75%, 100%), meal-day streak milestones (7, 30, 100 consecutive logged days), and the first meet of each weekly objective.

#### Scenario: Every source family qualifies

- GIVEN a user has qualifying history in all four source groups
- WHEN collectibles are derived
- THEN the catalogue MUST expose the corresponding achievement, checkpoint, streak, and weekly tokens

#### Scenario: Non-meal streak is present

- GIVEN a user has a weight or exercise streak but no qualifying meal-day run
- WHEN streak collectibles are derived
- THEN no meal-day milestone token MUST be earned from that other streak

### Requirement: R12 — Shelf and Latest-Earn Accent

Journey MUST always render the full shelf. Earned tokens MUST show artwork and unlock dates; locked tokens MUST show silhouettes. The World island MUST show the most recently earned token as an accent and MUST show no earned-token accent when none is earned.

#### Scenario: Mixed shelf renders

- GIVEN a user has earned some but not all tokens
- WHEN Journey loads
- THEN earned tokens MUST show artwork and dates
- AND remaining catalogue entries MUST show locked silhouettes

#### Scenario: World shows latest earn

- GIVEN multiple tokens have unlock dates
- WHEN the World island renders
- THEN its accent MUST represent the token with the latest unlock date

#### Scenario: Empty history remains useful

- GIVEN a user has earned no collectible
- WHEN Journey and World render
- THEN Journey MUST show the locked shelf and World MUST omit an earned-token accent

### Requirement: R13 — Earliest-Crossing Monotonicity

Unlocks MUST derive from the earliest retained historical crossing, including qualifying history present at activation. They MUST appear once, never duplicate, and never relock after live state reverses. Checkpoints MUST use the first weight at or below each threshold; meal milestones MUST use the day a chronological consecutive run first reaches its target; weekly tokens MUST use the earliest qualifying week.

#### Scenario: Checkpoint state reverses

- GIVEN weight first crosses 50%, later rises above it, and crosses again
- WHEN collectibles are derived
- THEN the 50% token MUST remain earned at the first crossing date

#### Scenario: Broken meal runs

- GIVEN a 29-day run breaks before a later 30-day run
- WHEN the 30-day token is derived
- THEN it MUST unlock on day 30 of the later run and remain earned after another break

#### Scenario: Retroactive activation

- GIVEN qualifying achievement, checkpoint, streak, or weekly history predates activation
- WHEN the shelf first loads
- THEN each qualifying token MUST already be earned at its earliest historical date
