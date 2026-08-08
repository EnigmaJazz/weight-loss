/* Frontend confetti-eligibility tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning the confetti gate
 * (design §Confetti, spec 'Confetti eligibility'): fire ONLY when the earned
 * checkpoint count increases since the previous load; suppress on first
 * render (no previous count) and on any non-increase. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { shouldCelebrate } = format;

test("shouldCelebrate suppresses on first render (null previous count)", () => {
  assert.equal(shouldCelebrate(null, 0), "suppress");
  assert.equal(shouldCelebrate(null, 5), "suppress");
});

test("shouldCelebrate treats undefined previous count as first render", () => {
  assert.equal(shouldCelebrate(undefined, 3), "suppress");
});

test("shouldCelebrate fires when the earned count increases", () => {
  assert.equal(shouldCelebrate(2, 5), "fire");
  // A previous count of 0 is a real prior render, not a first render.
  assert.equal(shouldCelebrate(0, 1), "fire");
});

test("shouldCelebrate suppresses when the count is unchanged", () => {
  assert.equal(shouldCelebrate(5, 5), "suppress");
  assert.equal(shouldCelebrate(0, 0), "suppress");
});

test("shouldCelebrate suppresses when the count decreases", () => {
  assert.equal(shouldCelebrate(5, 3), "suppress");
  assert.equal(shouldCelebrate(4, 0), "suppress");
});
