/* Frontend auth-gate form validation tests — node:test (stdlib), no framework.
 * Imports the REAL static/auth.js the SPA uses, pinning the client-side
 * username/password rules against the backend's contract (routes.py
 * RegisterIn: username 3-32 chars after strip().lower(), no whitespace;
 * password >= 8 chars, untrimmed). */
import { test } from "node:test";
import assert from "node:assert/strict";
import auth from "../../static/auth.js";

const {
  normalizeUsername,
  validateUsername,
  validatePassword,
  normalizeEmail,
  validateEmail,
} = auth;

/* ---- normalizeUsername -------------------------------------------------- */

test("normalizeUsername trims and lowercases mixed-case input", () => {
  assert.equal(normalizeUsername("  Alice "), "alice");
});

test("normalizeUsername lowercases already-trimmed input", () => {
  assert.equal(normalizeUsername("BOB"), "bob");
});

test("normalizeUsername is null-safe", () => {
  assert.equal(normalizeUsername(null), "");
  assert.equal(normalizeUsername(undefined), "");
});

/* ---- validateUsername --------------------------------------------------- */

test("validateUsername accepts a plain valid username", () => {
  assert.equal(validateUsername("alice"), null);
});

test("validateUsername accepts the 3-character minimum", () => {
  assert.equal(validateUsername("bob"), null);
});

test("validateUsername accepts the 32-character maximum", () => {
  assert.equal(validateUsername("a".repeat(32)), null);
});

test("validateUsername trims a trailing space before validating", () => {
  // mirrors backend strip(): "alice " is a valid username
  assert.equal(validateUsername("alice "), null);
});

test("validateUsername rejects a 2-character username", () => {
  const err = validateUsername("ab");
  assert.match(err, /3-32/);
});

test("validateUsername rejects a 33-character username", () => {
  const err = validateUsername("a".repeat(33));
  assert.match(err, /3-32/);
});

test("validateUsername rejects internal whitespace", () => {
  const err = validateUsername("al ice");
  assert.match(err, /space/);
});

test("validateUsername rejects empty and null input", () => {
  assert.match(validateUsername(""), /3-32/);
  assert.match(validateUsername(null), /3-32/);
});

/* ---- validatePassword --------------------------------------------------- */

test("validatePassword accepts a password of at least 8 characters", () => {
  assert.equal(validatePassword("password123"), null);
});

test("validatePassword accepts exactly 8 characters", () => {
  assert.equal(validatePassword("12345678"), null);
});

test("validatePassword does not trim — trailing spaces count as characters", () => {
  // mirrors backend: len(value) < 8 on the raw string
  assert.equal(validatePassword("1234567 "), null);
});

test("validatePassword rejects a 7-character password", () => {
  const err = validatePassword("1234567");
  assert.match(err, /8/);
});

test("validatePassword rejects empty and null input", () => {
  assert.match(validatePassword(""), /8/);
  assert.match(validatePassword(null), /8/);
});

/* ---- normalizeEmail / validateEmail ------------------------------------- */

test("normalizeEmail trims and lowercases mixed-case input", () => {
  assert.equal(normalizeEmail("  Alice@Example.COM "), "alice@example.com");
});

test("normalizeEmail is null-safe", () => {
  assert.equal(normalizeEmail(null), "");
  assert.equal(normalizeEmail(undefined), "");
});

test("validateEmail accepts a plain valid address", () => {
  assert.equal(validateEmail("alice@example.com"), null);
});

test("validateEmail accepts a one-letter domain label", () => {
  assert.equal(validateEmail("a@b.co"), null);
});

test("validateEmail rejects addresses without a dot in the domain", () => {
  // mirrors backend: basic local@domain.tld format required
  assert.match(validateEmail("a@b"), /email/);
});

test("validateEmail rejects missing local or domain parts", () => {
  assert.match(validateEmail("@example.com"), /email/);
  assert.match(validateEmail("alice@"), /email/);
});

test("validateEmail rejects whitespace inside the address", () => {
  assert.match(validateEmail("a b@example.com"), /email/);
});

test("validateEmail rejects empty and null input", () => {
  assert.match(validateEmail(""), /email/);
  assert.match(validateEmail(null), /email/);
});
