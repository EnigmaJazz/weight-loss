# Delta for Game Appearance

## ADDED Requirements

### Requirement: R1 Quest and Progress Surface Styling

The Today `#quests-card` and XP chip plus Journey `#xp-card`, `#momentum-card`, and `#quest-history-card` MUST use existing semantic color, spacing, radius, elevation, typography, and state tokens. New CSS MUST introduce no hardcoded hex colors, MUST remain compatible with `[data-theme="dark"]`, and MUST neutralize new transitions and celebratory motion under `prefers-reduced-motion: reduce`.

#### Scenario: Tokens and dark mode

- GIVEN either light or dark theme is active
- WHEN the R1 cards, statuses, controls, and chip render
- THEN their colors MUST resolve from existing tokens with readable contrast and no new hex literal

#### Scenario: Reduced motion

- GIVEN reduced motion is requested
- WHEN quests change status or progress values update
- THEN new movement and transitions MUST be neutralized without hiding state changes

## MODIFIED Requirements

### Requirement: Motivation Surfaces and Mascot

The system MUST apply game styling to the header (fox mascot + playful lockup), summary scoreboard, streak tiles (flame treatment), reward chips (pop-in) + progress track, primary buttons, and auth/onboarding cards including the wizard step indicator. Primary buttons MUST apply press physics (`transform: scale(~0.97)` on `:active`), and flame pulse MUST render only while the streak is active via its data attribute. Today MUST remain a goals dashboard: Summary houses the hero ring, Streaks retains larger flame + count with `.flame` and `dataset.streakActive`, and Checkpoints houses the five-card milestone track. Styling MUST also cover Today quests + XP and Journey XP/momentum/history, without a new tab, mascot reactions, or backend styling changes. Visible copy, DOM ids, `[hidden]` contracts, dark-mode compatibility, and token-only styling MUST be preserved.

(Previously: Motivation styling covered the goals dashboard and existing tracker surfaces, but not R1 quest, XP, momentum, or quest-history surfaces.)

#### Scenario: Mascot, flame, copy

- GIVEN the served SPA after the change
- WHEN smoke selectors and visible-text pins run
- THEN mascot and flame elements MUST remain, flame pulse MUST be active-state gated, and pinned strings MUST remain unchanged

#### Scenario: Today tab remains goals dashboard

- GIVEN the served Today tab
- WHEN its cards are inspected
- THEN Summary MUST retain the hero ring, Streaks MUST retain `.flame` and `dataset.streakActive`, Checkpoints MUST retain the milestone track, and quests/XP MUST be added without a new tab

#### Scenario: Journey progression surfaces integrate

- GIVEN the served Journey tab
- WHEN its existing and R1 cards are inspected
- THEN XP, momentum, and quest history MUST join the existing layout without removing existing Journey surfaces
