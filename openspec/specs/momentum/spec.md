# Momentum Specification

## Purpose

Classify daily engagement without a brittle consecutive-day streak.

## Requirements

### Requirement: Daily Action Count

For a user and local date, actions MUST equal done quests plus that user's weight, exercise, meal, mood, and habit rows dated that day. Each quest and row MUST count once; records owned by another user MUST NOT count.

#### Scenario: Count quests and logs

- GIVEN a user has one done quest and one meal row today
- WHEN today's actions are counted
- THEN the action count MUST be 2

#### Scenario: Exclude another user

- GIVEN another user has actions on the same date
- WHEN the first user's momentum is calculated
- THEN the other user's records MUST NOT affect the result

### Requirement: Momentum Tiers

A day with assigned quests MUST be `Spark` at one action, `Good Day` at two or more actions, and `Great Day` when every current assigned quest is done and at least one action exists. `Great Day` MUST take precedence over lower tiers. A date with no assigned quests MUST have tier `none`, regardless of logs. Replaced rows are not current assignments; skipped quests prevent Great Day.

#### Scenario: Tier boundaries

- GIVEN assigned quests exist with zero, one, and two actions on separate dates
- WHEN tiers are calculated
- THEN the dates MUST resolve to `none`, `Spark`, and `Good Day`

#### Scenario: Great Day and skipped edge

- GIVEN all current quests are done on one date and one current quest is skipped on another
- WHEN tiers are calculated with at least one action each
- THEN the first MUST be `Great Day` and the second MUST NOT be `Great Day`

### Requirement: Trailing Successful-Day Window

`Good Day` and `Great Day` MUST be successful; `Spark` and `none` MUST not. The momentum window MUST contain 21 consecutive local calendar dates ending today, including today, and the successful count MUST be recalculated from those dates.

#### Scenario: Inclusive 21-day math

- GIVEN 18 of the dates from today minus 20 days through today are Good or Great
- WHEN momentum is calculated
- THEN `successful_days` MUST be 18 and `window_days` MUST be 21

#### Scenario: Exclude day 22

- GIVEN a successful day occurred today minus 21 days
- WHEN today's window is calculated
- THEN that day MUST NOT contribute

### Requirement: Momentum API

Authenticated `GET /api/momentum` MUST return `today_tier`, `successful_days`, and `window_days` for only the current user.

#### Scenario: No quests today

- GIVEN no quests are assigned today
- WHEN `/api/momentum` is requested
- THEN `today_tier` MUST be `none` while `window_days` remains 21
