/* Weight Loss Tracker — pure display formatters shared by the SPA and tests.
 * Classic-script UMD: assigns `WeightFormat` on globalThis for the browser and
 * `module.exports` for node:test. static/index.html loads this BEFORE app.js. */
"use strict";
(function (global) {
  function fmt1(v) {
    return v == null ? "—" : Number(v).toFixed(1);
  }

  /** "82.5 kg (181.9 lb)" or "82.5 kg (13 st 0.4 lb)" from flat keys;
   * null-safe. displayUnit picks which imperial form follows kg: "lb" (total
   * pounds, the default) or "st-lb" (stones + pounds). In st-lb mode the
   * breakdown only appears when there is at least one whole stone — "0 st
   * 1.1 lb" would duplicate the lb already shown — so sub-stone values fall
   * back to total lb. */
  function weightLabel(kg, lb, stone, stoneLb, displayUnit) {
    if (kg == null) return "—";
    const stLbMode = displayUnit === "st-lb";
    const parts = [];
    parts.push(`${fmt1(kg)} kg`);
    if (stLbMode && stone != null && stoneLb != null && Math.round(stone) > 0) {
      parts.push(`${Math.round(stone)} st ${fmt1(stoneLb)} lb`);
    } else if (lb != null) {
      parts.push(`${fmt1(lb)} lb`);
    }
    return parts.length > 1 ? `${parts[0]} (${parts.slice(1).join("; ")})` : parts[0];
  }

  /** Summary rows use prefixed keys: prefix_kg, prefix_lb, prefix_stone, prefix_stone_lb. */
  function summaryLabel(o, prefix, displayUnit) {
    return weightLabel(o[`${prefix}_kg`], o[`${prefix}_lb`], o[`${prefix}_stone`], o[`${prefix}_stone_lb`], displayUnit);
  }

  /** The imperial form of one weight WITHOUT the kg prefix: "181.9 lb" in lb
   * mode, or "13 st 0.4 lb" in st-lb mode when there is at least one whole
   * stone (sub-stone values fall back to total lb, mirroring weightLabel).
   * Pure display helper for summary sub-lines; null lb -> "". */
  function weightImperial(lb, stone, stoneLb, displayUnit) {
    if (lb == null) return "";
    if (displayUnit === "st-lb" && stone != null && Math.round(stone) > 0) {
      return `${Math.round(stone)} st ${fmt1(stoneLb)} lb`;
    }
    return `${fmt1(lb)} lb`;
  }

  /** stone + lb -> kg. The exact international pound (1 lb = 0.45359237 kg),
   * inverse of units.py's KG_TO_LB = 2.2046226218. Null-safe, rounding-free
   * (raw value; display rounding is the SPA's job). */
  function stoneLbToKg(stone, lb) {
    if (stone == null || lb == null) return null;
    return (stone * 14 + lb) * 0.45359237;
  }

  /** ft + in -> cm (1 in = 2.54 cm exactly). Null-safe, rounding-free. */
  function ftInToCm(ft, inches) {
    if (ft == null || inches == null) return null;
    return (ft * 12 + inches) * 2.54;
  }

  /** API "YYYY-MM-DD" -> "DD/MM/YY" (zero-padded day/month, two-digit year).
   * Null-safe (missing date renders ""); a full timestamp or any other input
   * that starts with an ISO date is formatted from its date part, and
   * non-ISO input passes through unchanged so a contract violation surfaces
   * instead of crashing the UI. */
  function formatDate(isoDate) {
    if (isoDate == null) return "";
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(isoDate));
    if (!match) return String(isoDate);
    const [, year, month, day] = match;
    return `${day}/${month}/${String(year).slice(-2)}`;
  }

  /** Resolve a persisted unit preference; missing/empty falls back to the
   * project default (kg / cm) so the app opens in the user's format. */
  function unitPref(value, fallback) {
    return value === null || value === undefined || value === "" ? fallback : value;
  }

  /** The API returns entries newest-first (the history list shows them that
   * way); the chart reads left -> right in time, so it plots this reversed
   * copy — oldest on the left, newest on the right. Never mutates input. */
  function chronological(entries) {
    return entries.slice().reverse();
  }

  /** The Monday ("YYYY-MM-DD") of the ISO week an entry's date falls in. JS
   * lacks Python's date.isocalendar(), so compute it from the weekday: days
   * since Monday = (getDay() + 6) % 7, then subtract. Parsed as UTC so the
   * result is deterministic in every timezone. */
  function isoWeekStart(isoDate) {
    const [year, month, day] = String(isoDate).slice(0, 10).split("-").map(Number);
    const d = new Date(Date.UTC(year, month - 1, day));
    d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(d.getUTCDate()).padStart(2, "0");
    return `${d.getUTCFullYear()}-${mm}-${dd}`;
  }

  /** Exercise entries -> total minutes per ISO week. Returns
   * [{ weekStart, minutes }] oldest -> newest; weekStart is the Monday of the
   * entry's ISO week. Input order is irrelevant and the input is never
   * mutated. */
  function exerciseMinutesPerWeek(entries) {
    const byWeek = new Map();
    for (const e of entries) {
      const weekStart = isoWeekStart(e.date);
      byWeek.set(weekStart, (byWeek.get(weekStart) || 0) + e.duration_min);
    }
    return [...byWeek.entries()]
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([weekStart, minutes]) => ({ weekStart, minutes }));
  }

  /** Meal entries -> total calories per calendar date. Returns
   * [{ date, calories }] oldest -> newest. The input is never mutated. */
  function caloriesPerDay(entries) {
    const byDay = new Map();
    for (const e of entries) {
      const date = String(e.date).slice(0, 10);
      byDay.set(date, (byDay.get(date) || 0) + e.calories);
    }
    return [...byDay.entries()]
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([date, calories]) => ({ date, calories }));
  }

  /** Target kg for a BMI at a height — mirrors units.weight_kg_from_bmi:
   * round(bmi*(h/100)**2, 1). None when either input is unset. Drives the
   * wizard's BMI-mode derived-weight hint, so it must match the server. */
  function weightKgFromBmi(bmi, heightCm) {
    if (bmi == null || heightCm == null) return null;
    const meters = heightCm / 100;
    return Math.round(bmi * meters * meters * 10) / 10;
  }

  /** BMI = kg / (m)^2 — mirrors units.calculate_bmi; None when the weight is
   * unset or the height is unset/non-positive. */
  function bmiFromKg(weightKg, heightCm) {
    if (weightKg == null || heightCm == null || heightCm <= 0) return null;
    const meters = heightCm / 100;
    return weightKg / (meters * meters);
  }

  /** Healthy BMI band (18.5-24.9) expressed in kg — mirrors
   * units.healthy_weight_range. [minKg, maxKg]; null when height is unset. */
  function healthyRange(heightCm) {
    if (heightCm == null) return null;
    const meters = heightCm / 100;
    return [
      Math.round(18.5 * meters * meters * 10) / 10,
      Math.round(24.9 * meters * meters * 10) / 10,
    ];
  }

  /** BMI bucket: underweight (<18.5), healthy (18.5-24.9), overweight (>=25)
   * — mirrors units.classify_bmi. Null input -> null. */
  function classifyBmi(bmi) {
    if (bmi == null) return null;
    if (bmi < 18.5) return "underweight";
    if (bmi <= 24.9) return "healthy";
    return "overweight";
  }

  /** Shared healthy-range hint used by the onboarding wizard AND the settings
   * goal form. targetStatus is the classification ("healthy" |
   * "underweight" | "overweight"): the API's summary.target_status when
   * available, otherwise classifyBmi() of the entered target. Returns null
   * when the healthy range is unknown (height unset); with a target it flags
   * under/overweight targets, without one it still surfaces the range. */
  function targetRangeHint(targetKg, healthyMinKg, healthyMaxKg, targetStatus) {
    if (healthyMinKg == null || healthyMaxKg == null) return null;
    const range = `${fmt1(healthyMinKg)}-${fmt1(healthyMaxKg)} kg`;
    if (targetKg == null || targetStatus == null) {
      return { outOfRange: false, status: null, message: `Healthy range: ${range}.` };
    }
    if (targetStatus === "underweight" || targetStatus === "overweight") {
      const side = targetStatus === "overweight" ? "above" : "below";
      return {
        outOfRange: true,
        status: targetStatus,
        message: `Target is ${side} the healthy range (${range}).`,
      };
    }
    return {
      outOfRange: false,
      status: "healthy",
      message: `Target is within the healthy range (${range}).`,
    };
  }

  /** Python's round(x, 4) — round half to even (banker's rounding). Mirrors
   * rewards.checkpoint_thresholds' `round(..., 4)` so threshold kg matches
   * the server. Private: not part of the public api surface. */
  function round4(value) {
    const factor = 10000;
    const scaled = value * factor;
    const floored = Math.floor(scaled);
    const frac = scaled - floored;
    if (frac < 0.5) return floored / factor;
    if (frac > 0.5) return (floored + 1) / factor;
    return (floored % 2 === 0 ? floored : floored + 1) / factor;
  }

  /** 0..1 goal progress: (baseline − current) / (baseline − target), clamped
   * to 0..1 so overshoot never exceeds 100% and weight gain floors at 0;
   * null when any input is missing OR baseline <= target (no loss goal). */
  function goalProgress(baseline, current, target) {
    if (baseline == null || current == null || target == null || baseline <= target) {
      return null;
    }
    const pct = (baseline - current) / (baseline - target);
    return Math.max(0, Math.min(1, pct));
  }

  /** Threshold kg per checkpoint — mirrors rewards.checkpoint_thresholds:
   * baseline − (p/100)·(baseline − target), banker's-rounded to 4dp, for p in
   * 10/25/50/75/100; [] when inputs are missing or target >= baseline. */
  function checkpointThresholds(baseline, target) {
    if (baseline == null || target == null || target >= baseline) return [];
    const totalLoss = baseline - target;
    return [10, 25, 50, 75, 100].map((percent) =>
      round4(baseline - (percent / 100) * totalLoss)
    );
  }

  /** kg -> {lb, stone, stoneLb} — mirrors units.kg_to_stone incl. the 14-lb
   * carry snap (a float epsilon a hair below an exact stone lands on the
   * whole stone, not "9 st 14 lb"). Raw values; display rounding is the
   * SPA's job. Null-safe. */
  function kgToImperial(kg) {
    if (kg == null) return null;
    const lb = kg * 2.2046226218;
    let stone = Math.floor(lb / 14);
    let stoneLb = lb - 14 * stone;
    if (stoneLb >= 14 - 1e-6) {
      stone += 1;
      stoneLb = 0.0;
    }
    return { lb, stone, stoneLb };
  }

  /** The milestone strip's next line: "Next: 50% at 90.0 kg (14 st 2.4 lb)"
   * from the raw threshold kg + display unit (same weightLabel path the
   * milestone dots use). The all-earned copy ("All checkpoints earned!") is
   * the caller's concern — it has no percent. Null-safe: missing percent or
   * kg -> "" (no goal data renders no next line). */
  function milestoneNextLabel(percent, kg, displayUnit) {
    if (percent == null || kg == null) return "";
    const imp = kgToImperial(kg);
    return `Next: ${percent}% at ${weightLabel(kg, imp.lb, imp.stone, imp.stoneLb, displayUnit)}`;
  }

  /** Achievements read-diff (design §Celebration): the keys newly present in
   * the earned-key set since the previous successful read. null/undefined
   * previous suppresses the first render; set subtraction ignores unchanged
   * and lost keys so only genuinely new unlocks are returned. Pure, no side
   * effects. */
  function newAchievementKeys(previous, current) {
    if (previous == null) return [];
    const prev = new Set(previous);
    return (current ?? []).filter((key) => !prev.has(key));
  }

  /** Confetti eligibility gate (design §Confetti): "fire" only when the
   * earned checkpoint count increased since the previous load; the first
   * render (null/undefined previous count) is always "suppress". Equal or
   * lower counts are also suppressed. */
  function shouldCelebrate(prevEarned, curEarned) {
    if (prevEarned == null) return "suppress";
    return curEarned > prevEarned ? "fire" : "suppress";
  }

  /** Resolve a three-state theme preference to a concrete light/dark choice.
   * An explicit light/dark pref always wins; "system" (or any unknown pref)
   * follows the OS color scheme via systemPref ("dark" | "light"); an
   * unavailable/null systemPref resolves to light (the no-JS default). */
  function resolveTheme(pref, systemPref) {
    if (pref === "dark") return "dark";
    if (pref === "light") return "light";
    return systemPref === "dark" ? "dark" : "light";
  }

  /* ---- XP level curve mirrors (r1-quests-xp S4a) ----
   * Pure mirrors of xp.py + constants.py (LEVEL_XP_PER_LEVEL/LEVEL_XP_STEP),
   * pinned by tests/frontend/xp.test.mjs against tests/test_xp.py so the XP
   * chip's level/progress can never drift from the backend (spec 'XP Summary
   * Chip and Mirrors'). The chip renders the backend's title directly — only
   * the numeric curve needs mirroring client-side. */
  const LEVEL_XP_PER_LEVEL = 100; // mirrors constants.LEVEL_XP_PER_LEVEL
  const LEVEL_XP_STEP = 50; // mirrors constants.LEVEL_XP_STEP

  /** Cumulative XP at which ``level`` starts — mirrors xp.threshold_for_level:
   * T(1) = 0 and T(L) = sum_{k=1}^{L-1} (100 + (k-1)*50), i.e. 25*(L-1)*(L+2).
   * The (L-1)*(L-2) product is always even, so the /2 division is exact. */
  function thresholdForLevel(level) {
    return (
      LEVEL_XP_PER_LEVEL * (level - 1) +
      (LEVEL_XP_STEP * (level - 1) * (level - 2)) / 2
    );
  }

  /** Greatest level L >= 1 whose start threshold is not above ``totalXp`` —
   * mirrors xp.level_from_xp: L = floor((isqrt(225 + 4*X) - 5) / 10), clamped
   * to at least 1. Math.sqrt of a perfect square is exact in IEEE 754, so
   * Math.floor(Math.sqrt(n)) equals Python's integer isqrt for every XP total
   * the app can reach (n < 2^52), keeping the 100/250/450 boundaries exact. */
  function levelFromXp(totalXp) {
    const root = Math.floor(Math.sqrt(225 + 4 * totalXp));
    return Math.max(1, Math.floor((root - 5) / 10));
  }

  /** (xpIntoNext, nextLevelAt) for ``totalXp`` — mirrors xp.level_progress:
   * XP earned into the current level and the absolute XP the next level
   * starts at (both derived from the threshold mirror above). */
  function xpIntoNext(totalXp) {
    const level = levelFromXp(totalXp);
    return {
      xpIntoNext: totalXp - thresholdForLevel(level),
      nextLevelAt: thresholdForLevel(level + 1),
    };
  }

  /* ---- World island stage bands (r2-world-xp-island S1) ----
   * Total XP where each stage begins — mirrors the LEVEL_TITLES bands from
   * the world-island-ui spec 'Five XP Stages': 1 Sprout 0-699, 2 Explorer
   * 700-2699, 3 Adventurer 2700-10449, 4 Champion 10450-23199, 5 Legend
   * 23200+. Pure numeric banding like the XP mirrors above; pinned by
   * tests/frontend/world.test.mjs against the spec boundary vectors. */
  const WORLD_STAGE_THRESHOLDS = [700, 2700, 10450, 23200];

  /** World island stage (1-5) for a total XP total. */
  function worldStage(totalXp) {
    return 1 + WORLD_STAGE_THRESHOLDS.filter((t) => totalXp >= t).length;
  }

  /** World stage-up confetti eligibility (game-appearance spec 'World stage
   * diff'): "fire" only when the stage strictly increased between consecutive
   * successfully rendered stages; first render (null/undefined previous), a
   * failed read (null/undefined current), an unchanged stage, and a lower
   * stage all "suppress". Mirrors shouldCelebrate's fire/suppress contract. */
  function stageChanged(previous, current) {
    if (previous == null || current == null) return "suppress";
    return current > previous ? "fire" : "suppress";
  }

  /* ---- Quest domain icons (r2-completion S1, spec 'Quest Icons' R1) ----
   * Decorative inline-SVG glyphs for the nine quest domains. Array-of-
   * ["domain", "svg"] pairs so the SPA gate test can regex-extract and
   * ast.literal_eval the exact literal (drift-guard mirror of the
   * EXERCISE_TYPES/HABIT_TYPES convention): the SVG strings stay simple —
   * no `]`, no backslashes, single-quoted attributes inside double-quoted
   * strings. Icons fill from currentColor so the SPA's token CSS tints
   * them; they are decorative (aria-hidden at the call site), never a
   * substitute for the domain text. */
  const QUEST_DOMAIN_ICONS = [
    ["exercise", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><path d='M13 2 4 13h6l-2 9 9-11h-6l2-9z'/></svg>"],
    ["nutrition", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><circle cx='12' cy='13.5' r='8'/><path d='M12 5.5c1.5-2.5 5-3 6.5-2-.5 2-2 3.5-4.5 3.5-1 0-1.8-.5-2-1.5z'/></svg>"],
    ["movement", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><ellipse cx='9' cy='8.5' rx='4' ry='3'/><circle cx='4.5' cy='6.5' r='1.4'/><circle cx='4' cy='9.5' r='1.4'/><circle cx='5.7' cy='11.7' r='1.4'/><ellipse cx='13.5' cy='17' rx='2.6' ry='2.2'/></svg>"],
    ["routine", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect x='4' y='5' width='16' height='15' rx='2' fill='none' stroke='currentColor' stroke-width='2'/><path d='M8 3v4M16 3v4' stroke='currentColor' stroke-width='2' stroke-linecap='round'/><path d='M9 14l2.2 2.2L15.5 11' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/></svg>"],
    ["wellbeing", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><path d='M12 20.5S4.8 16 3 12.1C1.4 8.6 3.4 4.5 7 4.5c2 0 3.6 1.1 4.5 2.7l.5.8.5-.8c.9-1.6 2.5-2.7 4.5-2.7 3.6 0 5.6 4.1 4 7.6C19.2 16 12 20.5 12 20.5z'/></svg>"],
    ["weight", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><path d='M12 3v14M5 6h14' stroke='currentColor' stroke-width='2' stroke-linecap='round'/><path d='M5 6 2.5 11h5zM19 6l2.5 5h-5zM8 17h8'/></svg>"],
    ["strength", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><path d='M4 10h16v4H4z'/><path d='M2 8h3v8H2zM19 8h3v8h-3z'/></svg>"],
    ["sleep", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><path d='M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z'/><path d='M18.5 5l.5 1.2 1.2.5-1.2.5-.5 1.2-.5-1.2-1.2-.5 1.2-.5.5-1.2z'/></svg>"],
    ["recovery", "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='currentColor'><path d='M5 19C5 10 10 5 19 5c0 9-5 14-14 14z'/><path d='M5 19c3-6 7-10 12-12' fill='none' stroke='currentColor' stroke-width='1.5' stroke-linecap='round'/></svg>"],
  ];

  /** Resolve the decorative inline SVG for a quest domain by EXACT lookup
   * (spec 'Quest Icons' R1): the stored domain maps without translation or
   * aliasing, and an unknown domain throws instead of falling back — a
   * missing icon must fail loudly at render time, never substitute. */
  function iconForDomain(domain) {
    for (const [key, svg] of QUEST_DOMAIN_ICONS) {
      if (key === domain) return svg;
    }
    throw new Error(`Unknown quest domain: ${domain}`);
  }

  const api = { fmt1, weightLabel, summaryLabel, weightImperial, stoneLbToKg, ftInToCm, formatDate, unitPref, chronological, exerciseMinutesPerWeek, caloriesPerDay, weightKgFromBmi, bmiFromKg, healthyRange, classifyBmi, targetRangeHint, goalProgress, checkpointThresholds, kgToImperial, milestoneNextLabel, newAchievementKeys, shouldCelebrate, resolveTheme, thresholdForLevel, levelFromXp, xpIntoNext, worldStage, stageChanged, QUEST_DOMAIN_ICONS, iconForDomain };
  if (typeof module === "object" && module.exports) module.exports = api;
  if (global) global.WeightFormat = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
