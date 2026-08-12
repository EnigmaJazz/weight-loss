/* Frontend World island stage tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses. Pins the pure stage
 * contract (world-island-ui spec 'Five XP Stages' + game-appearance spec
 * 'World stage diff'): worldStage bands total XP on the LEVEL_TITLES
 * thresholds (0/700/2700/10450/23200) and stageChanged gates stage-up
 * confetti to strictly-increasing successful renders. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { worldStage, stageChanged } = format;

/* ---- worldStage (world-island-ui spec 'Five XP Stages') ------------------- */

test("worldStage maps 0/699/700/2699/2700/10449/10450/23199/23200 to stages 1..5", () => {
  // Both sides of every band boundary: 0-699 -> 1, 700-2699 -> 2,
  // 2700-10449 -> 3, 10450-23199 -> 4, 23200+ -> 5 (LEVEL_TITLES bands).
  assert.equal(worldStage(0), 1);
  assert.equal(worldStage(699), 1);
  assert.equal(worldStage(700), 2);
  assert.equal(worldStage(2699), 2);
  assert.equal(worldStage(2700), 3);
  assert.equal(worldStage(10449), 3);
  assert.equal(worldStage(10450), 4);
  assert.equal(worldStage(23199), 4);
  assert.equal(worldStage(23200), 5);
});

/* ---- stageChanged (game-appearance spec 'World stage diff') --------------- */

test("stageChanged suppresses on first render (null/undefined previous stage)", () => {
  assert.equal(stageChanged(null, 2), "suppress");
  assert.equal(stageChanged(undefined, 2), "suppress");
});

test("stageChanged suppresses a failed read (null/undefined current stage)", () => {
  assert.equal(stageChanged(2, null), "suppress");
  assert.equal(stageChanged(2, undefined), "suppress");
});

test("stageChanged fires when the stage increases to the next stage", () => {
  assert.equal(stageChanged(2, 3), "fire");
});

test("stageChanged fires on any increase between successful renders", () => {
  // The spec fires on ANY stage increase (consecutive successful renders),
  // so a multi-band jump still celebrates once instead of being lost.
  assert.equal(stageChanged(1, 3), "fire");
});

test("stageChanged suppresses an unchanged stage (repeated render)", () => {
  assert.equal(stageChanged(3, 3), "suppress");
});

test("stageChanged suppresses a lower stage", () => {
  assert.equal(stageChanged(4, 3), "suppress");
});
