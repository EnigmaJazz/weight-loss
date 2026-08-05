# Delta for Weight Tracking

## ADDED Requirements

### Requirement: Authenticated Weight and Settings APIs

Every weight and settings endpoint MUST require an authenticated user. `GET /api/weight`, `POST /api/weight`, `DELETE /api/weight/{entry_id}`, `GET /api/settings`, and `PUT /api/settings` MUST read or mutate only that user's data. Unauthenticated requests MUST return status 401 without changing state.

#### Scenario: Reject unauthenticated weight access

- GIVEN no valid session
- WHEN any weight or settings endpoint is requested
- THEN the API MUST respond with status 401
- AND no weight or setting MUST be disclosed or changed

#### Scenario: Keep two users isolated

- GIVEN users A and B have different weights and settings
- WHEN user A reads weight history and settings
- THEN only user A's values MUST be returned

### Requirement: Legacy Pre-Auth Data Is Discarded on Migration

When a pre-auth database is migrated, all legacy rows MUST be discarded — no account inherits them. Every account, including the first, MUST start with an empty dataset and set its own target, height, and schedules. The discard MUST be atomic with the schema rebuild and MUST NOT run again on already-migrated databases.

#### Scenario: First account starts empty after migration

- GIVEN legacy settings and entries exist and no account exists
- WHEN the database is migrated and the first account is registered
- THEN the account MUST have no settings, entries, rewards, subscriptions, or dedupe rows

#### Scenario: Later accounts also start empty

- GIVEN a migrated database
- WHEN any account is registered
- THEN it MUST start with an empty dataset and no inherited data MUST change

## MODIFIED Requirements

### Requirement: Canonical Weight Mutations

The system MUST store one positive `weight_kg` value per date for each authenticated user. An upsert MUST create or replace only that user's value for the date, and a delete MUST remove only an entry owned by that user and recompute only that user's dependent summaries. The same date MAY exist once for each user.

(Previously: Weight uniqueness and mutations were defined globally for a single user.)

#### Scenario: Create and update one date

- GIVEN no entry exists for an authenticated user on a valid date
- WHEN 80 kg and then 79 kg are upserted by that user for that date
- THEN exactly one of that user's entries MUST remain with canonical value 79 kg

#### Scenario: Delete an entry

- GIVEN an owned entry contributes to the authenticated user's history and summary
- WHEN that user deletes the entry
- THEN it MUST disappear and only that user's history and summary MUST be recomputed

#### Scenario: Reject cross-user deletion

- GIVEN an entry belongs to user B
- WHEN authenticated user A deletes its identifier
- THEN the API MUST respond with status 404 and preserve the entry
