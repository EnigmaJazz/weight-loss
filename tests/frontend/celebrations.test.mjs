/* Frontend celebration-queue tests — node:test (stdlib), imports the REAL
 * static/format.js. Pins S6 pure layer (R14-R18): suppression on first
 * render/unchanged/failed reads, current order, R18 priority + purity. */
import { test } from "node:test";
import assert from "node:assert/strict";
import format from "../../static/format.js";

const { questStatusChanged, weeklyMetDiff, collectibleKeysetDiff, enqueueCelebrations } = format;
const qs = (prev, cur) => questStatusChanged(prev, cur);

test("questStatusChanged suppresses first render, unknown ids, non-done, failed reads", () => {
  assert.deepEqual(qs(null, [{ id: 1, status: "done" }]), []);
  assert.deepEqual(qs([{ id: 1, status: "open" }], null), []);
  assert.deepEqual(qs([{ id: 1, status: "open" }], undefined), []);
  assert.deepEqual(qs([{ id: 1, status: "open" }], [{ id: 1, status: "open" }, { id: 99, status: "done" }]), []);
  assert.deepEqual(qs([{ id: 1, status: "done" }], [{ id: 1, status: "done" }]), []);
  assert.deepEqual(qs([{ id: 1, status: "open" }], [{ id: 1, status: "skipped" }]), []);
});

test("questStatusChanged emits open/skipped->done once, in current order", () => {
  assert.deepEqual(qs([{ id: 1, status: "open" }, { id: 2, status: "open" }, { id: 3, status: "open" }], [{ id: 1, status: "done" }, { id: 2, status: "done" }, { id: 3, status: "open" }]), [{ questId: 1 }, { questId: 2 }]);
  assert.deepEqual(qs([{ id: 7, status: "skipped" }], [{ id: 7, status: "done" }]), [{ questId: 7 }]);
});

test("weeklyMetDiff emits newly met goals only, in current order", () => {
  assert.deepEqual(weeklyMetDiff(null, ["quests"]), []);
  assert.deepEqual(weeklyMetDiff(["quests"], ["quests", "good_days"]), [{ goal: "good_days" }]);
  assert.deepEqual(weeklyMetDiff(["quests"], ["quests"]), []);
  assert.deepEqual(weeklyMetDiff(["quests", "good_days"], ["quests"]), []);
  assert.deepEqual(weeklyMetDiff(["good_days"], ["good_days", "quests"]), [{ goal: "quests" }]);
});

test("collectibleKeysetDiff emits newly earned keys only, in current order", () => {
  assert.deepEqual(collectibleKeysetDiff(null, ["getting_started"]), []);
  assert.deepEqual(collectibleKeysetDiff(["getting_started"], ["getting_started", "consistency"]), ["consistency"]);
  assert.deepEqual(collectibleKeysetDiff(["consistency"], ["consistency"]), []);
  assert.deepEqual(collectibleKeysetDiff(["getting_started", "consistency"], ["getting_started"]), []);
  assert.deepEqual(collectibleKeysetDiff(["consistency"], ["consistency", "getting_started", "explorer"]), ["getting_started", "explorer"]);
});

test("enqueueCelebrations orders level > achievement > weekly/collectible > quest", () => {
  assert.deepEqual(enqueueCelebrations([
    { type: "quest_delight", questId: 1 }, { type: "weekly_met", goal: "quests" }, { type: "achievement", key: "moving_forward", title: "Moving Forward" }, { type: "level_up", from: 1, to: 2, title: "Sprout" }, { type: "collectible_first_earn", keys: ["consistency"] },
  ]).map((ev) => ev.type), ["level_up", "achievement", "weekly_met", "collectible_first_earn", "quest_delight"]);
});

test("enqueueCelebrations stays stable within a tier, suppresses unknown/null, pure", () => {
  const input = [{ type: "collectible_first_earn", keys: ["a"] }, { type: "weekly_met", goal: "quests" }, { type: "quest_delight", questId: 2 }, { type: "mystery", payload: 1 }, { type: "quest_delight", questId: 1 }, { type: null }];
  const ordered = enqueueCelebrations(input);
  assert.deepEqual(ordered.map((ev) => ev.type), ["collectible_first_earn", "weekly_met", "quest_delight", "quest_delight"]);
  assert.deepEqual(ordered.slice(2).map((ev) => ev.questId), [2, 1]);
  assert.deepEqual(input.map((ev) => ev.type), ["collectible_first_earn", "weekly_met", "quest_delight", "mystery", "quest_delight", null]);
});

test("celebration events are plain serializable data (R17 static outcomes)", () => {
  for (const ev of enqueueCelebrations([
    { type: "level_up", from: 1, to: 2, title: "Sprout" }, { type: "achievement", key: "moving_forward", title: "Moving Forward" }, { type: "weekly_met", goal: "quests" }, { type: "collectible_first_earn", keys: ["consistency"], titles: ["Consistency"] }, { type: "quest_delight", questId: 1 },
  ])) {
    assert.deepEqual(ev, JSON.parse(JSON.stringify(ev)));
    assert.equal(Object.prototype.hasOwnProperty.call(ev, "animation"), false);
  }
});
