/* Frontend unit-input conversion tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning the st+lb->kg and
 * ft+in->cm conversions against the backend's canonical factors (units.py:
 * KG_TO_LB = 2.2046226218, i.e. 1 lb = 0.45359237 kg; 1 in = 2.54 cm). */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { stoneLbToKg, ftInToCm } = format;

function closeTo(actual, expected, eps = 1e-9) {
  assert.ok(
    Math.abs(actual - expected) <= eps,
    `expected ${actual} to be within ${eps} of ${expected}`
  );
}

test("stoneLbToKg converts 12 st 4 lb to the exact kg (172 lb x 0.45359237)", () => {
  closeTo(stoneLbToKg(12, 4), 78.01788764);
});

test("stoneLbToKg converts whole stones (13 st 0 lb = 182 lb)", () => {
  closeTo(stoneLbToKg(13, 0), 82.55381134);
});

test("stoneLbToKg converts pounds-only (0 st 8 lb)", () => {
  closeTo(stoneLbToKg(0, 8), 3.62873896);
});

test("stoneLbToKg boundary lb = 13.9 (just under 14) converts", () => {
  closeTo(stoneLbToKg(10, 13.9), 69.807865743);
});

test("stoneLbToKg converts lb = 14 at the helper level; >= 14 is rejected by the form (app.js)", () => {
  closeTo(stoneLbToKg(10, 14), (10 * 14 + 14) * 0.45359237);
});

test("stoneLbToKg zero inputs convert to 0 (combined > 0 is the form's job)", () => {
  assert.equal(stoneLbToKg(0, 0), 0);
});

test("ftInToCm converts 5 ft 10 in to 177.8 cm", () => {
  closeTo(ftInToCm(5, 10), 177.8);
});

test("ftInToCm converts 6 ft 0 in to 182.88 cm", () => {
  closeTo(ftInToCm(6, 0), 182.88);
});

test("ftInToCm converts inches-only (0 ft 5 in = 12.7 cm)", () => {
  closeTo(ftInToCm(0, 5), 12.7);
});

test("ftInToCm zero inputs convert to 0", () => {
  assert.equal(ftInToCm(0, 0), 0);
});

test("helpers are null-safe for null and undefined inputs", () => {
  assert.equal(stoneLbToKg(null, 4), null);
  assert.equal(stoneLbToKg(12, null), null);
  assert.equal(stoneLbToKg(undefined, undefined), null);
  assert.equal(ftInToCm(null, 10), null);
  assert.equal(ftInToCm(5, null), null);
  assert.equal(ftInToCm(undefined, undefined), null);
});
