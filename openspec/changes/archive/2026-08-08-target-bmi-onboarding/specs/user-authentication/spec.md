# Delta for user-authentication

## MODIFIED Requirements

### Requirement: Authentication API

`POST /api/auth/login` MUST verify credentials, `GET /api/auth/me` MUST return the authenticated identity and a `needs_onboarding` boolean, and `POST /api/auth/logout` MUST revoke the current session and clear its cookie. `needs_onboarding` MUST be true when the authenticated user has no `onboarding_complete` settings row and false when that row is true.

(Previously: `/api/auth/me` returned only the authenticated identity.)

#### Scenario: Login and identify the account

- GIVEN an account with valid credentials
- WHEN those credentials are submitted and `/api/auth/me` is requested
- THEN login MUST establish a session and `me` MUST return that account

#### Scenario: Reject incorrect credentials

- GIVEN an existing account
- WHEN login receives an incorrect password
- THEN the API MUST respond with status 401 and establish no session

#### Scenario: Logout revokes access

- GIVEN an authenticated session
- WHEN logout succeeds and that session is reused
- THEN the session MUST be rejected with status 401

#### Scenario: me reports onboarding state

- GIVEN an account with no onboarding_complete row
- WHEN `/api/auth/me` is requested with a valid session
- THEN the response MUST include needs_onboarding true

#### Scenario: me reports completed onboarding

- GIVEN an account whose onboarding_complete row is true
- WHEN `/api/auth/me` is requested with a valid session
- THEN the response MUST include needs_onboarding false