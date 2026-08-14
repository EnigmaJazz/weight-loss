# Celebration Queue Specification

## Purpose

Deliver meaningful reward moments sequentially, once per transition, while respecting reduced motion.

## Requirements

### Requirement: R14 — Level-Up Banner

A level increase MUST show a non-blocking banner naming the landing level and title, including after multi-level jumps. It MUST appear once per transition, auto-dismiss after approximately three seconds, and dismiss on tap.

#### Scenario: Multi-level landing

- GIVEN one transition crosses multiple level thresholds
- WHEN the celebration is shown
- THEN the banner MUST name only the landing level and title

#### Scenario: Banner dismissal

- GIVEN a level-up banner is visible
- WHEN about three seconds pass or the user taps it
- THEN it MUST dismiss without blocking other interaction

### Requirement: R15 — Quest-Completion Delight

Changing a quest from incomplete to done MUST show one brief checkmark delight on that quest card. Repeated completion or unchanged reads MUST NOT replay it.

#### Scenario: Quest completes once

- GIVEN an open quest card is visible
- WHEN its status becomes done
- THEN one completion delight MUST appear on that card

### Requirement: R16 — Achievement Toast

A newly unlocked achievement MUST show one toast alongside the existing confetti. Existing achievements on the initial successful read and unchanged later reads MUST NOT toast.

#### Scenario: Achievement read diff

- GIVEN an initial successful read established the earned achievement set
- WHEN a later successful read contains a new achievement
- THEN one achievement toast MUST be queued with the existing confetti

### Requirement: R17 — Reduced-Motion Static Outcomes

When reduced motion is preferred, all celebration animation and confetti MUST be suppressed. Completed, earned, met, and level state MUST remain visible, and any banner, toast, or checkmark outcome MUST be presented statically.

#### Scenario: Reduced-motion quest completion

- GIVEN reduced motion is enabled
- WHEN a quest completes and triggers reward transitions
- THEN updated state and applicable celebration messages MUST remain visible without animation or confetti

### Requirement: R18 — Priority Queue and Transition Dedupe

Weekly meets MUST toast the 40-XP award, and first collectible earns MUST toast the token name. All celebrations MUST run sequentially with no overlap in this priority: level-up, achievement, weekly or collectible, then quest delight. Successful-read difference markers MUST emit each transition once and MUST NOT advance on failed reads.

#### Scenario: Simultaneous transitions

- GIVEN one refresh detects level-up, achievement, weekly or collectible, and quest events
- WHEN celebrations run
- THEN they MUST appear one at a time in the required priority order

#### Scenario: Reload after handled transition

- GIVEN transition markers record celebrations already handled
- WHEN unchanged state loads again
- THEN no handled celebration MUST replay

#### Scenario: Failed read preserves marker

- GIVEN a prior successful marker exists
- WHEN a refresh fails and a later successful refresh contains a new transition
- THEN the failed read MUST NOT consume that transition
