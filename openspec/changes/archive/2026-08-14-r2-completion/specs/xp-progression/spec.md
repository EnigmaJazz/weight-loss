# Delta for XP Progression

## MODIFIED Requirements

### Requirement: Derived XP

Total XP MUST equal the per-user sum of `xp_value` for quests whose status is `done` plus persisted `xp_awarded` values in `weekly_awards`. Open, skipped, and replaced quests MUST contribute zero. XP MUST NOT use a mutable general-purpose ledger or `reward_events`; `weekly_awards` MUST be the only award table included by this change.

(Previously: Total XP was derived only from done quests and prohibited every XP award ledger.)

#### Scenario: Sum completed quests and weekly awards

- GIVEN a user has done quests worth 20 and 40, skipped and replaced quests, and one weekly award worth 40
- WHEN XP is calculated
- THEN total XP MUST be 100

#### Scenario: Keep users isolated

- GIVEN users A and B have different completed quests and weekly awards
- WHEN user A requests XP
- THEN only user A's done quests and weekly awards MUST contribute
