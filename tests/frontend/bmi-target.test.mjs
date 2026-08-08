/* Frontend BMI-target helper tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning the client-side
 * wizard hints against the backend's canonical helpers in units.py
 * (weight_kg_from_bmi, healthy_weight_range, classify_bmi): the wizard shows
 * derived target weight + healthy range + under/overweight flag before the
 * API is ever called, so the JS arithmetic must match the server's. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { weightKgFromBmi, bmiFromKg, healthyRange, classifyBmi, targetRangeHint } = format;

function closeTo(actual, expected, eps = 1e-9) {
  assert.ok(
    Math.abs(actual - expected) <= eps,
    `expected ${actual} to be within ${eps} of ${expected}`
  );
}

test("weightKgFromBmi converts BMI 22 at 175 cm to 67.4 kg (spec value)", () => {
  assert.equal(weightKgFromBmi(22, 175), 67.4);
});

test("weightKgFromBmi converts the 18.5/200 boundary to exactly 74.0 kg (spec value)", () => {
  assert.equal(weightKgFromBmi(18.5, 200), 74.0);
});

test("weightKgFromBmi is null-safe when either input is unset", () => {
  assert.equal(weightKgFromBmi(null, 175), null);
  assert.equal(weightKgFromBmi(22, null), null);
  assert.equal(weightKgFromBmi(undefined, undefined), null);
});

test("bmiFromKg converts 70 kg at 175 cm to the exact BMI (22.857...)", () => {
  closeTo(bmiFromKg(70, 175), 70 / 3.0625);
});

test("bmiFromKg is null-safe for unset or non-positive height", () => {
  assert.equal(bmiFromKg(70, null), null);
  assert.equal(bmiFromKg(70, 0), null);
  assert.equal(bmiFromKg(null, 175), null);
});

test("healthyRange at 175 cm returns the spec band (56.7, 76.3) kg", () => {
  assert.deepEqual(healthyRange(175), [56.7, 76.3]);
});

test("healthyRange is null when height is unset", () => {
  assert.equal(healthyRange(null), null);
  assert.equal(healthyRange(undefined), null);
});

test("classifyBmi boundaries: 18.5 and 24.9 healthy, 25.0 overweight", () => {
  assert.equal(classifyBmi(18.5), "healthy");
  assert.equal(classifyBmi(24.9), "healthy");
  assert.equal(classifyBmi(25.0), "overweight");
});

test("classifyBmi below 18.5 is underweight; null input is null", () => {
  assert.equal(classifyBmi(18.4), "underweight");
  assert.equal(classifyBmi(null), null);
});

test("targetRangeHint flags a healthy target as in-range", () => {
  const hint = targetRangeHint(70, 56.7, 76.3, "healthy");
  assert.equal(hint.outOfRange, false);
  assert.match(hint.message, /within the healthy range \(56\.7-76\.3 kg\)/);
});

test("targetRangeHint flags an overweight target above the range", () => {
  const hint = targetRangeHint(90, 56.7, 76.3, "overweight");
  assert.equal(hint.outOfRange, true);
  assert.match(hint.message, /above the healthy range/);
});

test("targetRangeHint flags an underweight target below the range", () => {
  const hint = targetRangeHint(50, 56.7, 76.3, "underweight");
  assert.equal(hint.outOfRange, true);
  assert.match(hint.message, /below the healthy range/);
});

test("targetRangeHint is null when the healthy range is unknown", () => {
  assert.equal(targetRangeHint(70, null, 76.3, "healthy"), null);
  assert.equal(targetRangeHint(70, 56.7, null, null), null);
});

test("targetRangeHint with no target still surfaces the healthy range", () => {
  const hint = targetRangeHint(null, 56.7, 76.3, null);
  assert.equal(hint.outOfRange, false);
  assert.match(hint.message, /Healthy range: 56\.7-76\.3 kg\./);
});
