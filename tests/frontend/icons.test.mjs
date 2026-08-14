/* Quest-domain icon tests (quest-icons spec R1) against the real
 * static/format.js: pins the nine-domain catalogue, inline-SVG quality,
 * exact iconForDomain resolution, and fail-loud unknown domains. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { QUEST_DOMAIN_ICONS, iconForDomain } = format;
const DOMAINS = ["exercise", "nutrition", "movement", "routine", "wellbeing", "weight", "strength", "sleep", "recovery"];

test("QUEST_DOMAIN_ICONS pins nine distinct non-empty inline currentColor SVGs", () => {
  assert.deepEqual(QUEST_DOMAIN_ICONS.map(([d]) => d), DOMAINS);
  const svgs = QUEST_DOMAIN_ICONS.map(([, svg]) => svg);
  assert.equal(new Set(svgs).size, 9); // no aliasing
  for (const svg of svgs) {
    assert.ok(svg.trim().startsWith("<svg") && svg.includes("</svg>"));
    assert.ok(svg.includes("currentColor") && !/#[0-9a-fA-F]{3,8}\b/.test(svg));
  }
});

test("iconForDomain resolves the movement domain exactly", () => {
  const movement = QUEST_DOMAIN_ICONS.find(([d]) => d === "movement")[1];
  assert.equal(iconForDomain("movement"), movement);
});

test("iconForDomain throws on an unknown domain (no fallback or alias)", () => {
  assert.throws(() => iconForDomain("bogus"), /Unknown quest domain/);
});
