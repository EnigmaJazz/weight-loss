# Weekly Objectives Specification

## Purpose

Define per-user weekly progress, exactly-once XP awards, activation semantics, and user-facing status.

## Requirements

### Requirement: R5 — Mon–Sun Objectives

Each Monday–Sunday week MUST track two objectives: 10 done quests and 3 successful momentum days. Only existing Good or Great classifications MUST count; Spark and unclassified days MUST NOT count.

#### Scenario: Exact thresholds are met

- GIVEN a week has 10 done quests and 3 Good or Great days
- WHEN weekly progress is calculated
- THEN both objectives MUST be met

#### Scenario: Spark is excluded

- GIVEN a week contains a one-action Spark day or a day with no assigned quests
- WHEN successful days are counted
- THEN that day MUST NOT advance the good-days objective

### Requirement: R6 — Immediate Exactly-Once Awards

Each objective MUST award 40 XP at the moment it first becomes met, for at most 80 XP per week. Awards MUST persist in `weekly_awards`, remain isolated by user, and be paid exactly once per user, week, and objective. A newly paid objective MUST emit one weekly-met signal naming the 40-XP award.

#### Scenario: Tenth quest pays immediately

- GIVEN an eligible week has 9 done quests and no quest award
- WHEN the tenth quest becomes done
- THEN the objective MUST become met and total XP MUST increase by 40
- AND one weekly-met signal MUST be emitted

#### Scenario: Reconciliation repeats

- GIVEN an objective already has its persisted award
- WHEN weekly state is read or reconciled again, including after restart
- THEN XP MUST NOT increase and no new met signal MUST be emitted

### Requirement: R7 — Forward-Only Per-User Activation

The first weekly-state load MUST persist a per-user activation stamp. Pre-activation weeks MUST NOT award XP. If activation occurs after a Monday begins, that partial week MUST be exempt and the next Monday MUST begin the first counted week.

#### Scenario: Mid-week activation

- GIVEN a user's first weekly load occurs on Wednesday
- WHEN the current and earlier weeks are evaluated
- THEN neither MUST award XP, even if an objective was met
- AND the following Monday MUST start the first counted week

#### Scenario: Users activate independently

- GIVEN two users first load weekly state on different dates
- WHEN eligibility is calculated
- THEN each user's counted weeks MUST derive only from their own activation stamp

### Requirement: R8 — Today and Journey Surfaces

Today MUST show live current-week progress for both objectives. Journey MUST show current/latest status and weekly history, including met, unmet, and exempt states.

#### Scenario: Live progress is visible

- GIVEN an activated user has partial current-week progress
- WHEN Today and Journey load
- THEN Today MUST show both current counts and targets
- AND Journey MUST show the corresponding week status and history

### Requirement: R9 — First-Meet Collectible Eligibility

Each objective's earliest qualifying week MUST unlock one collectible. Historical pre-activation weeks MUST count for this collectible only; later meets MUST NOT create duplicates.

#### Scenario: Historical first meet

- GIVEN the good-days objective first qualified before activation
- WHEN collectible eligibility is evaluated
- THEN its token MUST use that historical week and award no historical XP
