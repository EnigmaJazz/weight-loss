/* Frontend XP mirror tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses. Pins the today-quests-ui
 * drift contract (spec 'XP Summary Chip and Mirrors'): format.js must mirror
 * xp.py's level curve EXACTLY, so the chip's level/progress can never diverge
 * from the backend. Every vector below matches tests/test_xp.py:
 *   - thresholdForLevel mirrors xp.threshold_for_level (T(L) = 25*(L-1)*(L+2))
 *   - levelFromXp mirrors xp.level_from_xp (99 -> 1, 100 -> 2, 250 -> 3)
 *   - xpIntoNext mirrors xp.level_progress (total - T(L), T(L+1)) */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { thresholdForLevel, levelFromXp, xpIntoNext } = format;

/* ---- thresholdForLevel (mirrors xp.threshold_for_level) ------------------- */

test("thresholdForLevel starts level 1 at 0 XP", () => {
  assert.equal(thresholdForLevel(1), 0);
});

test("thresholdForLevel matches the cumulative 100+(n-1)*50 curve", () => {
  // T(L) = 25*(L-1)*(L+2): 0, 100, 250, 450, 700 (backend test_threshold_vectors).
  assert.equal(thresholdForLevel(2), 100);
  assert.equal(thresholdForLevel(3), 250);
  assert.equal(thresholdForLevel(4), 450);
  assert.equal(thresholdForLevel(5), 700);
});

/* ---- levelFromXp (mirrors xp.level_from_xp) ------------------------------- */

test("levelFromXp boundary vectors match backend (99/100/250)", () => {
  // The spec's pinned drift vectors: totals 99, 100, 250 -> levels 1, 2, 3.
  assert.equal(levelFromXp(99), 1);
  assert.equal(levelFromXp(100), 2);
  assert.equal(levelFromXp(250), 3);
});

test("levelFromXp full boundary set matches backend", () => {
  assert.equal(levelFromXp(0), 1);
  assert.equal(levelFromXp(249), 2);
  assert.equal(levelFromXp(449), 3);
  assert.equal(levelFromXp(450), 4);
  assert.equal(levelFromXp(699), 4);
  assert.equal(levelFromXp(700), 5);
});

/* ---- xpIntoNext (mirrors xp.level_progress) ------------------------------- */

test("xpIntoNext reports progress within a level", () => {
  assert.deepEqual(xpIntoNext(80), { xpIntoNext: 80, nextLevelAt: 100 });
  assert.deepEqual(xpIntoNext(120), { xpIntoNext: 20, nextLevelAt: 250 });
});

test("xpIntoNext is exact at boundaries (backend test_progress_vectors)", () => {
  assert.deepEqual(xpIntoNext(0), { xpIntoNext: 0, nextLevelAt: 100 });
  assert.deepEqual(xpIntoNext(100), { xpIntoNext: 0, nextLevelAt: 250 });
  assert.deepEqual(xpIntoNext(250), { xpIntoNext: 0, nextLevelAt: 450 });
  assert.deepEqual(xpIntoNext(450), { xpIntoNext: 0, nextLevelAt: 700 });
});
