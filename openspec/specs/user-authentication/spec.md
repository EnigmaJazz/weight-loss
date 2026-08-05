# User Authentication Specification

## Purpose

Define registration, revocable password sessions, API protection, and the SPA authentication gate.

## Requirements

### Requirement: Account Registration

`POST /api/auth/register` MUST accept a 3–32 character username without whitespace and a password of at least 8 characters. Usernames MUST be lowercased and unique case-insensitively. Passwords MUST be persisted only as independently salted scrypt hashes, never as plaintext or reversible values. Registration MUST authenticate the account.

#### Scenario: Register a valid account

- GIVEN username `alice` is available
- WHEN `Alice` and a valid password are registered
- THEN the account MUST be created as `alice`
- AND the response MUST establish an authenticated session

#### Scenario: Reject invalid credentials

- GIVEN a username or password violates its length or whitespace rule
- WHEN registration is attempted
- THEN the API MUST respond with status 422 and create no account

#### Scenario: Reject a duplicate username

- GIVEN username `alice` already exists
- WHEN `ALICE` is registered
- THEN the API MUST respond with status 409 and create no account

### Requirement: Authentication API

`POST /api/auth/login` MUST verify credentials, `GET /api/auth/me` MUST return the authenticated identity, and `POST /api/auth/logout` MUST revoke the current session and clear its cookie.

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

### Requirement: Session Cookie Security

The session cookie MUST be `HttpOnly`, `SameSite=Lax`, `Path=/`, expire after 30 days, and set `Secure` according to configuration. Its random secret MUST NOT be persisted; only a SHA-256 hash MAY be stored. Expired sessions MUST be rejected.

#### Scenario: Issue a secure session

- GIVEN valid registration or login credentials
- WHEN a session is issued
- THEN its cookie MUST carry all configured attributes and a 30-day expiry
- AND persisted session state MUST contain only the secret hash

#### Scenario: Reject an expired session

- GIVEN a session has passed its expiry
- WHEN it is presented to an authenticated API
- THEN the API MUST respond with status 401

### Requirement: Protected API Authorization

Every existing data API plus `/api/auth/me` and `/api/auth/logout` MUST require a valid session. `require_user` MUST return 401, not 403, for a missing, invalid, or expired session. A user MUST NOT read or mutate another user's resources; ownership-hidden identifiers MUST respond with 404.

#### Scenario: Access without a session

- GIVEN no valid session cookie
- WHEN a protected `/api/*` endpoint is requested
- THEN the API MUST respond with status 401 and disclose no protected data

#### Scenario: Address another user's resource

- GIVEN user A is authenticated and a resource belongs to user B
- WHEN user A addresses that resource by identifier
- THEN the API MUST respond with status 404 and MUST NOT mutate it

### Requirement: SPA Authentication Gate

The SPA MUST determine login state through `/api/auth/me`, show registration/login when unauthenticated, and load tracker data only when authenticated. It MUST provide logout and return to the gate after logout or a protected 401 response.

#### Scenario: Open the SPA without authentication

- GIVEN the browser has no valid session
- WHEN the SPA initializes
- THEN tracker data MUST remain hidden and the authentication gate MUST be shown

#### Scenario: Session expires during use

- GIVEN the tracker is visible and its session expires
- WHEN a protected data request returns 401
- THEN the SPA MUST hide tracker data and show the authentication gate
