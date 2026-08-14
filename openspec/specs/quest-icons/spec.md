# Quest Icons Specification

## Purpose

Provide coherent, decorative quest-domain iconography and cartoon-fox artwork without changing quest semantics.

## Requirements

### Requirement: R1 — Nine-Domain Icon Catalogue

The client MUST provide distinct inline-SVG icons for `exercise`, `nutrition`, `movement`, `routine`, `wellbeing`, `weight`, `strength`, `sleep`, and `recovery`. It MUST map the stored domain value exactly, without aliases. Drift checks MUST pin the complete nine-domain set and the six-domain stored subset against the quest catalogue.

#### Scenario: Stored domain maps exactly

- GIVEN a quest whose stored domain is `movement`
- WHEN a quest card or history row renders
- THEN the movement icon MUST be shown without translating the domain

#### Scenario: Unknown domain is not aliased

- GIVEN a quest has a domain outside the nine-domain catalogue
- WHEN its icon is resolved
- THEN resolution MUST fail visibly rather than substitute another domain icon

### Requirement: R2 — Cartoon-Fox Rework

The geometric fox MUST be replaced coherently by a cartoon fox face in the favicon, header mascot, World island stage-5 fox, and generated PWA icons. Shape changes, PNG regeneration, and drift pins MUST be delivered atomically while preserving the existing palette.

#### Scenario: Every fox instance is coherent

- GIVEN the new fox artwork is shipped
- WHEN the favicon, header, Legend island, and PWA icons are inspected
- THEN every instance MUST use the cartoon-face treatment and existing palette

#### Scenario: Generated assets drift

- GIVEN generated PWA icon bytes do not match the pinned cartoon-fox source
- WHEN asset validation runs
- THEN validation MUST fail rather than accept mixed fox versions

### Requirement: R3 — Inline Static Delivery

Quest icons MUST ship as inline SVG through the existing static application, with no dependency, external request, or new image format.

#### Scenario: Offline icon rendering

- GIVEN the application static files are available without network access
- WHEN either quest surface renders
- THEN its domain icon MUST render without an external asset request

### Requirement: R4 — Decorative and Motion-Neutral Presentation

Every quest icon MUST be marked `aria-hidden` because domain text already supplies its meaning. Icons MUST remain static, and any new fox or icon motion MUST be neutralized under reduced motion without hiding artwork.

#### Scenario: Assistive technology sees no duplicate label

- GIVEN a quest displays domain text and an icon
- WHEN accessibility semantics are inspected
- THEN the icon MUST be hidden from the accessibility tree

#### Scenario: Reduced motion is enabled

- GIVEN the user prefers reduced motion
- WHEN quest and fox artwork render
- THEN the same static artwork MUST remain visible without animation
