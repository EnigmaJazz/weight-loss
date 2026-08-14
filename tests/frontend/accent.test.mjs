/* Accent normalization tests against the real SPA helper. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { resolveAccent } = format;

test("resolveAccent preserves every supported accent", () => {
  for (const accent of ["purple", "teal", "blue", "green", "orange"]) {
    assert.equal(resolveAccent(accent), accent);
  }
});

test("resolveAccent falls back to attribute-free green", () => {
  for (const value of [null, undefined, "", "pink", "PURPLE"]) {
    assert.equal(resolveAccent(value), "green");
  }
});
