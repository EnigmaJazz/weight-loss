/* Frontend achievements read-diff tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning the read-diff gate
 * (design §Celebration, spec 'Achievement key-set diff' + 'Achievement
 * non-earn transitions'): newAchievementKeys returns ONLY keys newly present
 * in the earned-key set since the previous successful read; null/undefined
 * previous suppresses the first read; unchanged, lost, and repeated sets stay
 * quiet. The checkpoint shouldCelebrate regression re-pins that the existing
 * count-based celebration path is untouched by the new helper. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { newAchievementKeys, shouldCelebrate } = format;

test("newAchievementKeys suppresses the first read (null/undefined previous)", () => {
  assert.deepEqual(newAchievementKeys(null, ["getting_started"]), []);
  assert.deepEqual(newAchievementKeys(undefined, ["getting_started"]), []);
});

test("newAchievementKeys returns nothing when both sets are empty", () => {
  assert.deepEqual(newAchievementKeys([], []), []);
});

test("newAchievementKeys identifies exactly the newly earned keys once", () => {
  // One new key among unchanged keys.
  assert.deepEqual(
    newAchievementKeys(["getting_started"], ["getting_started", "consistency"]),
    ["consistency"]
  );
  // Multiple new keys in one transition are all reported, in set order.
  assert.deepEqual(
    newAchievementKeys(
      ["getting_started"],
      ["getting_started", "comeback", "explorer"]
    ),
    ["comeback", "explorer"]
  );
});

test("newAchievementKeys suppresses an unchanged repeated render", () => {
  const prev = ["getting_started", "consistency", "personal_best"];
  assert.deepEqual(newAchievementKeys(prev, [...prev]), []);
  // Same keys, different order, is still an unchanged set.
  assert.deepEqual(
    newAchievementKeys(prev, ["personal_best", "getting_started", "consistency"]),
    []
  );
});

test("newAchievementKeys suppresses sets that only lose keys", () => {
  assert.deepEqual(
    newAchievementKeys(["getting_started", "consistency"], ["consistency"]),
    []
  );
  // A lost key alongside a new one still reports only the new key.
  assert.deepEqual(
    newAchievementKeys(
      ["getting_started", "consistency"],
      ["consistency", "explorer"]
    ),
    ["explorer"]
  );
});

test("newAchievementKeys treats a missing current payload as an empty set (quiet)", () => {
  assert.deepEqual(newAchievementKeys(["getting_started"], null), []);
  assert.deepEqual(newAchievementKeys(["getting_started"], undefined), []);
});

test("shouldCelebrate regression: the checkpoint count path is unchanged", () => {
  assert.equal(shouldCelebrate(null, 3), "suppress");
  assert.equal(shouldCelebrate(2, 3), "fire");
  assert.equal(shouldCelebrate(3, 3), "suppress");
  assert.equal(shouldCelebrate(4, 3), "suppress");
});
