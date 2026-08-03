/* Frontend formatter regression tests — node:test (stdlib), no framework.
 * Imports the REAL static/format.js the SPA uses, pinning the display contract
 * from openspec/changes/core-app/specs/weight-tracking/spec.md: kg (lb; st lb). */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { fmt1, weightLabel } = format;

test("weightLabel renders the full multi-unit shape kg (lb; st lb)", () => {
  assert.equal(weightLabel(82.5, 181.9, 13, 0.4), "82.5 kg (181.9 lb; 13 st 0.4 lb)");
});

test("weightLabel renders kg (lb) when no stone is present", () => {
  assert.equal(weightLabel(82.5, 181.9, null, null), "82.5 kg (181.9 lb)");
});

test("weightLabel is null-safe for missing kg", () => {
  assert.equal(weightLabel(null, null, null, null), "—");
  assert.equal(weightLabel(undefined, undefined, undefined, undefined), "—");
});

test("weightLabel renders bare kg when only kg is present", () => {
  assert.equal(weightLabel(82.5, null, null, null), "82.5 kg");
});

test("fmt1 rounds to one decimal (toFixed(1))", () => {
  assert.equal(fmt1(181.881), "181.9");
  assert.equal(fmt1(13.881), "13.9");
  assert.equal(fmt1(26.939), "26.9");
});

test("weightLabel rounds stone-lb via fmt1 (spec example)", () => {
  assert.equal(weightLabel(70, 154.3, 11, 0.3), "70.0 kg (154.3 lb; 11 st 0.3 lb)");
});
