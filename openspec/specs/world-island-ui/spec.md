# World Island UI Specification

## Purpose

Define the XP-driven island reward display on the existing World tab.

## Requirements

### Requirement: Five XP Stages

The World island MUST derive its stage exclusively from the current user's existing total XP using these bands:

| Stage | Name | Total XP |
|---|---|---|
| 1 | Sprout Isle | 0–699 |
| 2 | Explorer Isle | 700–2699 |
| 3 | Adventurer Isle | 2700–10449 |
| 4 | Champion Isle | 10450–23199 |
| 5 | Legend Isle | 23200+ |

The thresholds MUST remain aligned with the `LEVEL_TITLES` bands and MUST be covered at both sides of every boundary.

#### Scenario: Boundary mapping

- GIVEN total XP values `0`, `699`, `700`, `2699`, `2700`, `10449`, `10450`, `23199`, and `23200`
- WHEN the World stage is derived
- THEN the values MUST map respectively to stages `1`, `1`, `2`, `2`, `3`, `3`, `4`, `4`, and `5`

### Requirement: Island Evolution and Appearance

The existing `#tab-world` MUST replace its placeholder with one inline SVG island showing only the derived stage. Evolution MUST be monotonic: sprout, sapling, tree, lush island, then thriving island. The fox MUST appear only at Legend. Island colors MUST use semantic design tokens in light and dark themes; no new asset MAY be introduced. New visual motion MUST be neutralized under `prefers-reduced-motion: reduce` without hiding the current stage.

#### Scenario: Evolved island presentation

- GIVEN an authenticated user at Champion stage in either theme
- WHEN the World tab renders
- THEN Champion Isle MUST show its lush stage without Legend's fox, using token-derived colors

#### Scenario: Terminal stage

- GIVEN total XP is at least `23200`
- WHEN the World tab renders
- THEN Legend Isle MUST show the thriving final stage with the fox

### Requirement: Stage Progress Display

The island card MUST display its stage name and meaningful progress. Stage 1 MUST show progress toward the user's next level rather than `0 / 700` stage progress. Stages 2–4 MUST show XP progress toward the next stage threshold. Stage 5 MUST show a completed terminal-stage state rather than a nonexistent next threshold.

#### Scenario: New-user progress

- GIVEN a stage-1 user has `0` total XP and level progress `0 / 100`
- WHEN the island card renders
- THEN it MUST show Sprout Isle and `0 / 100` level progress

#### Scenario: Progress toward next island

- GIVEN a user has `1000` total XP
- WHEN the island card renders
- THEN it MUST show Explorer Isle and progress from `700` toward `2700` total XP

### Requirement: Stage-Up Celebration

The client MUST compare consecutive successfully rendered stages and MUST fire confetti once only when the stage increases. It MUST suppress confetti on the first render, unchanged or lower stages, repeated renders, failed XP reads, and reduced-motion sessions.

#### Scenario: Later stage increase

- GIVEN stage 2 was rendered successfully
- WHEN a later successful XP render derives stage 3
- THEN confetti MUST fire once and MUST NOT fire on the next unchanged render

#### Scenario: Suppressed transitions

- GIVEN no prior stage, a failed read, or a stage that does not increase
- WHEN celebration eligibility is evaluated
- THEN confetti MUST be suppressed

### Requirement: Frontend-Only Regression Contract

The World island MUST reuse the existing authenticated XP response for stage progression and MAY consume authenticated collectible state solely to show the most recently earned collectible as an accent. The tab set and order MUST remain unchanged, and the former coming-soon placeholder MUST remain absent. The contract MUST permit collectible and weekly-objective content, but this change MUST add no World expansion beyond the latest-earn accent and MUST add no World-specific backend, schema, asset, economy, Coach integration, or notification behavior. Automated stage-boundary, latest-accent, SPA-gate, and browser-smoke checks MUST cover the result.

#### Scenario: Existing contracts remain intact

- GIVEN the completed change
- WHEN frontend unit, SPA-gate, smoke, and existing regression suites run
- THEN island stage and tab contracts MUST pass without World-specific backend changes

#### Scenario: Latest collectible accents the island

- GIVEN a user has multiple earned collectibles with unlock dates
- WHEN the World island renders
- THEN the token with the latest unlock date MUST appear as the island accent

#### Scenario: No collectible has been earned

- GIVEN a user has no earned collectible
- WHEN the World island renders
- THEN no earned-token accent MUST be shown and XP stage presentation MUST remain unchanged
