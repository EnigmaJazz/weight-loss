# Delta for Game Appearance

## MODIFIED Requirements

### Requirement: Motion System and Reduced-Motion Gate

Confetti MUST fire only for a newly earned checkpoint or for achievement keys newly present in the earned-key set from a successful achievements read. Both celebration paths MUST be suppressed on first render and gated by `prefers-reduced-motion`. An unchanged set, a disappearing key, a failed read, or a repeated render MUST NOT fire achievement confetti. Flame pulse, card hover elevation, and chip pop-in MUST likewise be gated by `@media (prefers-reduced-motion: reduce)`. Toast and tab reveals MUST use JavaScript class swaps, MUST NOT use `@starting-style`, and MUST preserve `[hidden]`. Pure checkpoint and achievement confetti-eligibility helpers MUST be covered by `node:test`; achievement unlocks MUST NOT trigger server push.

(Previously: Confetti eligibility covered only increases in the checkpoint earned count, with first-render and reduced-motion suppression.)

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

#### Scenario: Reduced motion

- GIVEN `prefers-reduced-motion: reduce` is active
- WHEN checkpoint or achievement state changes
- THEN confetti, pulse, hover elevation, and pop-in MUST be neutralized, and no `@starting-style` MUST appear
