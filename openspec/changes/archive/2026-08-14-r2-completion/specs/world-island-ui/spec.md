# Delta for World Island UI

## MODIFIED Requirements

### Requirement: Frontend-Only Regression Contract

The World island MUST reuse the existing authenticated XP response for stage progression and MAY consume authenticated collectible state solely to show the most recently earned collectible as an accent. The tab set and order MUST remain unchanged, and the former coming-soon placeholder MUST remain absent. The contract MUST permit collectible and weekly-objective content, but this change MUST add no World expansion beyond the latest-earn accent and MUST add no World-specific backend, schema, asset, economy, Coach integration, or notification behavior. Automated stage-boundary, latest-accent, SPA-gate, and browser-smoke checks MUST cover the result.

(Previously: The regression contract categorically prohibited collectible and weekly-objective content and every new asset on the World.)

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
