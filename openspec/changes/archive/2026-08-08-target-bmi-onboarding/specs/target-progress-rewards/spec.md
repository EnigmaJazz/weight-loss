# Delta for target-progress-rewards

## MODIFIED Requirements

### Requirement: Checkpoint Thresholds

The system MUST define checkpoints `10%, 25%, 50%, 75%, 100%`. For checkpoint `p`, threshold kg MUST equal `start − p × (start − target)`. Start MUST be `start_weight_override` when configured, otherwise the earliest-dated weight entry. The `target` MUST be resolved through the shared `weight_kg_from_bmi` helper with `target_weight` precedence over `target_bmi`, so thresholds and summary can never disagree.

(Previously: target was read directly from `target_weight`; no BMI-derived target or precedence existed.)

#### Scenario: Use earliest entry

- GIVEN earliest weight 100 kg, target 80 kg, and no override
- WHEN thresholds are calculated
- THEN the 10% and 100% thresholds MUST be 98 kg and 80 kg

#### Scenario: Use configured override

- GIVEN earliest weight 100 kg, override 110 kg, and target 80 kg
- WHEN thresholds are calculated
- THEN 110 kg MUST be used as start for every checkpoint

#### Scenario: Resolve target from BMI

- GIVEN height_cm 175, target_bmi 22 (resolved target 67.4 kg), target_weight unset, start 100 kg
- WHEN thresholds are calculated
- THEN the thresholds MUST use 67.4 kg as target, matching the summary's target_kg

#### Scenario: Weight precedence overrides BMI

- GIVEN target_weight 80 kg AND target_bmi 22 with height 175 and start 100 kg
- WHEN thresholds are calculated
- THEN thresholds MUST use 80 kg as target, identical to the summary

## ADDED Requirements

### Requirement: Reward-Affecting Settings Keys

Changing any reward-affecting settings key through `PUT /api/settings` (or onboarding) MUST recompute the affected user's active checkpoint set. The reward-affecting keys MUST include `target_weight`, `start_weight_override`, and `target_bmi`. Reconciliation MUST add, revoke, or re-earn checkpoints only for the affected user and MUST NOT touch any other user's rewards.

#### Scenario: target_bmi change reconciles

- GIVEN a user has the 10% checkpoint active with target_weight 80 kg and start 100 kg
- WHEN the user persists target_bmi 24 with height 175 (resolved target 73.5 kg) and clears target_weight
- THEN the active rewards MUST be recomputed against 73.5 kg before the response returns

#### Scenario: target_bmi unset reconciles to null target

- GIVEN a user has active checkpoints driven by target_bmi
- WHEN the user clears target_bmi (and target_weight stays unset)
- THEN all active checkpoints MUST be revoked because the resolved target is null

#### Scenario: Isolated per-user reconciliation

- GIVEN users A and B both have active checkpoints
- WHEN user A changes target_bmi
- THEN only user A's rewards MUST be reconciled and user B's MUST remain unchanged