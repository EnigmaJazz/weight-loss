# Delta for game-appearance

## MODIFIED Requirements

### Requirement: Motion System and Reduced-Motion Gate

Confetti MUST fire only for a newly earned checkpoint, achievement keys newly present in the earned-key set from a successful achievements read, or an increase between consecutive successfully rendered World stages. All celebration paths MUST be suppressed on first render and gated by `prefers-reduced-motion`. An unchanged or lower World stage, an unchanged or disappearing achievement key, a failed read, or a repeated render MUST NOT fire confetti. Flame pulse, card hover elevation, chip pop-in, and World island motion MUST likewise be gated by `@media (prefers-reduced-motion: reduce)`. Toast and tab reveals MUST use JavaScript class swaps, MUST NOT use `@starting-style`, and MUST preserve `[hidden]`. Pure checkpoint, achievement, and stage confetti-eligibility helpers MUST be covered by `node:test`; achievements and World stage-ups MUST NOT trigger server push.

(Previously: Confetti eligibility covered newly earned checkpoints and achievement keys, but not World stage increases.)

#### Scenario: Checkpoint confetti eligibility

- GIVEN a prior checkpoint earned count
- WHEN the earned count increases
- THEN the checkpoint helper MUST return fire, while a first render with no prior count MUST return suppress

#### Scenario: Achievement key-set diff

- GIVEN a prior earned-key set and a later successful read
- WHEN one new key appears while other keys remain unchanged
- THEN achievement confetti MUST fire once for that transition and MUST NOT fire on the next unchanged render

#### Scenario: Achievement non-earn transitions

- GIVEN a failed read, first read, or later set that only loses a key
- WHEN achievement celebration eligibility is evaluated
- THEN confetti MUST be suppressed

#### Scenario: World stage diff

- GIVEN a prior successfully rendered World stage
- WHEN a later successful render increases the stage
- THEN stage-up confetti MUST fire once, while first, unchanged, lower, failed, and repeated renders MUST suppress it

#### Scenario: Reduced motion

- GIVEN `prefers-reduced-motion: reduce` is active
- WHEN checkpoint, achievement, or World stage state changes
- THEN confetti, pulse, hover elevation, pop-in, and island motion MUST be neutralized, and no `@starting-style` MUST appear
