/* Weight Loss Tracker — auth-gate form validation, shared by the SPA and
 * node:test. Classic-script UMD: assigns `AuthForm` on globalThis for the
 * browser and `module.exports` for node:test. static/index.html loads this
 * BEFORE app.js.
 *
 * Rules mirror routes.py RegisterIn/LoginIn exactly:
 *   username: strip().lower() then 3-32 chars, no whitespace
 *   password: at least 8 characters (raw, untrimmed) */
"use strict";
(function (global) {
  const USERNAME_MIN = 3;
  const USERNAME_MAX = 32;
  const PASSWORD_MIN = 8;

  /** Trim + lowercase, the backend's normalize step. Null-safe. */
  function normalizeUsername(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  /** Returns an error message string, or null when the username is valid. */
  function validateUsername(value) {
    const username = normalizeUsername(value);
    if (username.length < USERNAME_MIN || username.length > USERNAME_MAX) {
      return `Username must be ${USERNAME_MIN}-${USERNAME_MAX} characters`;
    }
    if (/\s/.test(username)) {
      return "Username must not contain spaces";
    }
    return null;
  }

  /** Returns an error message string, or null when the password is valid.
   * Password is NOT trimmed: trailing spaces count as characters, exactly
   * like the backend's `len(value) < 8` check. */
  function validatePassword(value) {
    if (String(value ?? "").length < PASSWORD_MIN) {
      return `Password must be at least ${PASSWORD_MIN} characters`;
    }
    return null;
  }

  const api = { normalizeUsername, validateUsername, validatePassword };
  if (typeof module === "object" && module.exports) module.exports = api;
  if (global) global.AuthForm = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
