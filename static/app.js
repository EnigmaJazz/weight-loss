/* Weight Loss Tracker — vanilla JS SPA.
 * Formats the API's raw values (kg + lb + stone + BMI) for display.
 * Rounding to one decimal is done here, never in the API. */
"use strict";

const $ = (id) => document.getElementById(id);
const toastEl = $("toast");

/* Exercise-type allowlist mirroring constants.EXERCISE_TYPES (the drift guard
 * test pins this literal to the server constant). Drives the exercise <select>
 * in the log form; the server validates against the same allowlist. */
const EXERCISE_TYPES = ["walk", "run", "gym", "cycling", "swim", "other"];

/* Habit-type allowlist mirroring constants.HABIT_TYPES (the drift guard test
 * pins this literal to the server constant, same as EXERCISE_TYPES). The habit
 * check-in UI that consumes it ships with the Today surface (S4a); until then
 * the literal only pins the catalogue so UI and server cannot drift. */
const HABIT_TYPES = ["water", "fruit_veg", "home_cooked", "sleep_routine"];

/* ---- formatting -------------------------------------------------------- */
/* fmt1/weightLabel/summaryLabel live in static/format.js (index.html loads it
 * before app.js) so node:test can pin the exact display contract. */
const { fmt1, weightLabel, weightImperial, stoneLbToKg, ftInToCm, formatDate, unitPref, chronological, exerciseMinutesPerWeek, caloriesPerDay, weightKgFromBmi, bmiFromKg, healthyRange, classifyBmi, targetRangeHint, goalProgress, checkpointThresholds, kgToImperial, milestoneNextLabel, newAchievementKeys, shouldCelebrate, resolveTheme, thresholdForLevel, levelFromXp, xpIntoNext, worldStage, stageChanged, iconForDomain, questStatusChanged, weeklyMetDiff, collectibleKeysetDiff, enqueueCelebrations, habitLabel, validateMood } = globalThis.WeightFormat;
const {
  normalizeUsername,
  validateUsername,
  validatePassword,
  normalizeEmail,
  validateEmail,
} = globalThis.AuthForm;

/* Which imperial form follows kg in every weight label: "lb" (total pounds)
 * or "st-lb" (stones + pounds). Set from the persisted settings on each
 * loadData(); the default is lb mode. */
let displayUnit = "lb";

function bmiLabel(bmi) {
  return bmi == null ? "—" : fmt1(bmi);
}

function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  // Class-swap reveal: paint the base state first so the .is-visible
  // opacity/transform transition actually animates (no @starting-style).
  if (reducedMotion()) toastEl.classList.add("is-visible");
  else requestAnimationFrame(() => toastEl.classList.add("is-visible"));
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    toastEl.classList.remove("is-visible");
    toastEl.hidden = true;
  }, 3000);
}

/* Celebration queue (S6): producers stage, one flush per load plays level >
 * achievement > weekly/collectible > quest (R18); reduced motion in show layer. */

let celebrationQueue = [];
let celebrationProcessing = false;
let bannerResolve = null;
let bannerTimer = null;

function enqueueCelebrationEvents(events) {
  celebrationQueue.push(...(events ?? []));
}

async function flushCelebrationQueue() {
  if (celebrationProcessing) return;
  celebrationProcessing = true;
  try {
    while (celebrationQueue.length) {
      celebrationQueue = enqueueCelebrations(celebrationQueue);
      await showCelebration(celebrationQueue.shift());
    }
  } finally {
    celebrationProcessing = false;
  }
}

const wait = (ms = 3000) => new Promise((resolve) => setTimeout(resolve, ms));

async function showCelebration(ev) {
  const show = {
    level_up: () => showCelebrationBanner(`Level ${ev.to} · ${ev.title}`),
    achievement: () => { if (!reducedMotion()) fireConfetti(); toast(`Achievement unlocked: ${ev.title}`); },
    weekly_met: () => toast(ev.goal === "quests" ? "Weekly quests met! +40 XP" : "Good days met! +40 XP"),
    collectible_first_earn: () => toast(`Collectible earned: ${(ev.titles ?? []).join(", ")}`),
    quest_delight: () => showQuestDelight(ev.questId),
  }[ev.type];
  if (!show) return;
  // level_up holds the queue until the banner dismisses (auto ~3s or tap).
  if (ev.type === "level_up") return show();
  show();
  return wait(ev.type === "quest_delight" ? 1000 : 3000);
}

function drainCelebrationSignals() {
  const events = weeklyMetSignals.splice(0).map((s) => ({ type: "weekly_met", goal: s.goal }));
  for (const s of collectibleSignals.splice(0)) {
    events.push({ type: "collectible_first_earn", keys: s.keys, titles: s.titles ?? [] });
  }
  return events;
}

function hideCelebrationBanner() {
  const banner = $("celebration-banner");
  banner.classList.remove("is-visible");
  banner.hidden = true;
  const done = bannerResolve;
  bannerResolve = null;
  if (done) done();
}

function showCelebrationBanner(text) {
  const banner = $("celebration-banner");
  banner.textContent = text;
  banner.hidden = false;
  if (reducedMotion()) banner.classList.add("is-visible");
  else requestAnimationFrame(() => banner.classList.add("is-visible"));
  return new Promise((resolve) => {
    bannerResolve = resolve;
    clearTimeout(bannerTimer);
    bannerTimer = setTimeout(hideCelebrationBanner, 3000);
  });
}

$("celebration-banner").addEventListener("click", () => {
  clearTimeout(bannerTimer);
  hideCelebrationBanner();
});

/* Quest-completion delight (R15): one brief checkmark; reduced-motion users
 * get the same checkmark statically. */
function showQuestDelight(questId) {
  const row = document.querySelector(`#quests-card .quest-row[data-quest-id="${questId}"]`);
  if (!row) return;
  const mark = document.createElement("span");
  mark.className = "quest-delight";
  mark.setAttribute("aria-hidden", "true");
  mark.textContent = "✓";
  if (reducedMotion()) return row.append(mark);
  mark.classList.add("is-animating");
  mark.addEventListener("animationend", () => mark.remove());
  row.append(mark);
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    // Session missing/expired/revoked: hide the tracker and return to the
    // gate. Also reached by a wrong-password login, where the gate is already
    // visible — harmless, the caller surfaces the actual error.
    showAuthScreen();
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) {
      /* keep statusText */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

/* ---- authentication gate ------------------------------------------------ */

const authScreen = $("auth-screen");
const trackerEl = $("tracker");
const onboardingScreen = $("onboarding-screen");
const authForm = $("auth-form");
let authMode = "login";
let resetToken = null;

function setAuthMode(mode) {
  authMode = mode;
  const signup = mode === "signup";
  $("auth-title").textContent = signup ? "Create account" : "Log in";
  $("auth-submit").textContent = signup ? "Create account" : "Log in";
  $("auth-toggle").textContent = signup ? "Log in" : "Create account";
  $("auth-password").autocomplete = signup ? "new-password" : "current-password";
  // The email field belongs to signup (registration requires it); login needs
  // only username + password. Toggle required so the hidden field never blocks
  // submit (a hidden required input makes the browser refuse the form).
  $("auth-email").hidden = !signup;
  $("auth-email-label").hidden = !signup;
  $("auth-email").required = signup;
}

function showAuthForm() {
  $("auth-form").hidden = false;
  $("forgot-form").hidden = true;
  $("reset-form").hidden = true;
}

function showForgotForm() {
  setAuthMode("login");
  $("auth-form").hidden = true;
  $("forgot-form").hidden = false;
  $("reset-form").hidden = true;
}

function showResetForm() {
  setAuthMode("login");
  $("auth-form").hidden = true;
  $("forgot-form").hidden = true;
  $("reset-form").hidden = false;
}

function showAuthScreen() {
  authScreen.hidden = false;
  onboardingScreen.hidden = true;
  trackerEl.hidden = true;
  $("logout-btn").hidden = true;
  showAuthForm();
}

function showTracker() {
  authScreen.hidden = true;
  onboardingScreen.hidden = true;
  trackerEl.hidden = false;
  $("logout-btn").hidden = false;
  // A fresh login always lands on the Today tab.
  switchTab("today");
}

async function submitAuth(ev) {
  ev.preventDefault();
  const username = normalizeUsername($("auth-username").value);
  const password = $("auth-password").value;
  const usernameError = validateUsername(username);
  const passwordError = validatePassword(password);
  if (usernameError) {
    toast(usernameError);
    return;
  }
  if (passwordError) {
    toast(passwordError);
    return;
  }
  const body = { username, password };
  if (authMode === "signup") {
    const email = normalizeEmail($("auth-email").value);
    const emailError = validateEmail(email);
    if (emailError) {
      toast(emailError);
      return;
    }
    body.email = email;
  }
  const endpoint = authMode === "signup" ? "/api/auth/register" : "/api/auth/login";
  try {
    await fetchJson(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("auth-password").value = "";
    // A fresh account (or a pre-existing one without an onboarding row) is
    // flagged needs_onboarding and lands in the wizard, not the tracker.
    const me = await fetchJson("/api/auth/me");
    if (enterApp(me)) await loadData();
  } catch (err) {
    toast(`${authMode === "signup" ? "Signup" : "Login"} failed: ${err.message}`);
  }
}

async function submitForgot(ev) {
  ev.preventDefault();
  const email = normalizeEmail($("forgot-email").value);
  const emailError = validateEmail(email);
  if (emailError) {
    toast(emailError);
    return;
  }
  try {
    const res = await fetchJson("/api/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    // Always the same generic message — the API never reveals whether the
    // email is registered, and neither does the UI.
    $("forgot-email").value = "";
    toast(res.message || "If that email exists, a reset link is on its way");
  } catch (err) {
    toast(`Request failed: ${err.message}`);
  }
}

async function submitReset(ev) {
  ev.preventDefault();
  const password = $("reset-password").value;
  const passwordError = validatePassword(password);
  if (passwordError) {
    toast(passwordError);
    return;
  }
  if (password !== $("reset-confirm").value) {
    toast("Passwords do not match");
    return;
  }
  try {
    await fetchJson("/api/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: resetToken, password }),
    });
    resetToken = null;
    $("reset-password").value = "";
    $("reset-confirm").value = "";
    setAuthMode("login");
    showAuthForm();
    toast("Password reset — log in with your new password");
  } catch (err) {
    toast(`Reset failed: ${err.message}`);
  }
}

async function logout() {
  try {
    await fetchJson("/api/auth/logout", { method: "POST" });
  } catch (_) {
    /* session already gone — the gate still opens below */
  }
  setAuthMode("login");
  $("auth-username").value = "";
  $("auth-password").value = "";
  showAuthScreen();
}

/* ---- onboarding wizard --------------------------------------------------- */

const WIZARD_STEPS = ["height", "weight", "target", "goals-lifestyle", "units", "notifications"];

function showOnboarding() {
  authScreen.hidden = true;
  trackerEl.hidden = true;
  onboardingScreen.hidden = false;
  $("logout-btn").hidden = true;
  showWizardStep("height");
}

function showWizardStep(step) {
  for (const el of document.querySelectorAll(".wizard-step")) {
    el.hidden = el.dataset.step !== step;
  }
  // Sync the dot indicator: the active dot gets .is-current + aria-current
  // (dots are non-text, so the state must be exposed to assistive tech).
  for (const dot of document.querySelectorAll(".wizard-indicator li")) {
    const active = dot.dataset.step === step;
    dot.classList.toggle("is-current", active);
    if (active) dot.setAttribute("aria-current", "step");
    else dot.removeAttribute("aria-current");
  }
  if (step === "target") updateWizardRangeHint();
}

function currentWizardStep() {
  for (const el of document.querySelectorAll(".wizard-step")) {
    if (!el.hidden) return el.dataset.step;
  }
  return null;
}

/* Shared gate for init() and submitAuth: a flagged user gets the wizard and
 * the tracker stays hidden (spec: tracker data MUST stay hidden until
 * completion); everyone else lands on the tracker. Returns true when the
 * tracker was shown. */
function enterApp(me) {
  if (me?.needs_onboarding) {
    showOnboarding();
    return false;
  }
  showTracker();
  return true;
}

/* DOM readers for the wizard payload — the same conversions saveGoal/addEntry
 * use, so the submitted height/weight/target match what the API expects. */
function wizardHeightCm() {
  if (checkedRadio("ob-height-unit") === "ft-in") {
    const ft = $("ob-height-ft").value.trim();
    const inches = $("ob-height-in").value.trim();
    if (ft === "" || inches === "") return null;
    return ftInToCm(Number(ft), Number(inches));
  }
  const raw = $("ob-height-cm").value.trim();
  return raw === "" ? null : Number(raw);
}

function wizardWeightKg() {
  if (checkedRadio("ob-weight-unit") === "st-lb") {
    const stone = $("ob-weight-stone").value.trim();
    const lb = $("ob-weight-lb").value.trim();
    if (stone === "" || lb === "") return null;
    return stoneLbToKg(Number(stone), Number(lb));
  }
  const raw = $("ob-weight-kg").value.trim();
  return raw === "" ? null : Number(raw);
}

function wizardTargetKg() {
  if (checkedRadio("ob-target-mode") === "bmi") return null;
  if (checkedRadio("ob-target-unit") === "st-lb") {
    const stone = $("ob-target-stone").value.trim();
    const lb = $("ob-target-lb").value.trim();
    if (stone === "" || lb === "") return null;
    return stoneLbToKg(Number(stone), Number(lb));
  }
  const raw = $("ob-target-weight").value.trim();
  return raw === "" ? null : Number(raw);
}

/* Optional goals/lifestyle readers (spec user-onboarding): empty values are
 * sent as null / [] so the backend's defaults apply and a re-POST clears. */
function wizardPrimaryGoal() {
  return $("ob-primary-goal").value.trim() || null;
}

function wizardActivityLevel() {
  return $("ob-activity-level").value.trim() || null;
}

/* Values of every checked box in a named group, in DOM order (the backend
 * round-trips JSON lists with order preserved). */
function checkedValues(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(
    (el) => el.value
  );
}

/* One step at a time: validation runs on advance, so the Finish path (or the
 * form's Enter-to-advance submit) can trust every earlier step passed. */
function validateWizardStep(step) {
  if (step === "height") {
    if (checkedRadio("ob-height-unit") === "ft-in") {
      const ftRaw = $("ob-height-ft").value.trim();
      const inRaw = $("ob-height-in").value.trim();
      if (ftRaw === "" || inRaw === "") return "Enter both feet and inches for your height";
      const ft = Number(ftRaw);
      const inches = Number(inRaw);
      if (!(ft >= 0)) return "Feet must be 0 or more";
      if (!(inches >= 0) || inches >= 12) return "Inches must be at least 0 and less than 12";
    } else if (!(Number($("ob-height-cm").value) > 0)) {
      return "Enter your height in cm";
    }
    return null;
  }
  if (step === "weight") {
    if (checkedRadio("ob-weight-unit") === "st-lb") {
      const stoneRaw = $("ob-weight-stone").value.trim();
      const lbRaw = $("ob-weight-lb").value.trim();
      if (stoneRaw === "" || lbRaw === "") return "Enter both stone and pounds for your current weight";
      const stone = Number(stoneRaw);
      const lb = Number(lbRaw);
      if (!Number.isInteger(stone) || stone < 0) return "Stone must be a whole number, 0 or more";
      if (!(lb >= 0) || lb >= 14) return "Pounds must be at least 0 and less than 14";
      if (stone === 0 && lb === 0) return "Weight must be greater than 0";
    } else if (!(Number($("ob-weight-kg").value) > 0)) {
      return "Enter your current weight in kg";
    }
    return null;
  }
  if (step === "target") {
    if (checkedRadio("ob-target-mode") === "bmi") {
      const bmi = Number($("ob-target-bmi").value);
      if (!(bmi > 10 && bmi <= 40)) return "Target BMI must be greater than 10 and at most 40";
    } else if (checkedRadio("ob-target-unit") === "st-lb") {
      const stoneRaw = $("ob-target-stone").value.trim();
      const lbRaw = $("ob-target-lb").value.trim();
      if (stoneRaw === "" || lbRaw === "") return "Enter both stone and pounds for the target";
      const stone = Number(stoneRaw);
      const lb = Number(lbRaw);
      if (!Number.isInteger(stone) || stone < 0) return "Target stone must be a whole number, 0 or more";
      if (!(lb >= 0) || lb >= 14) return "Target pounds must be at least 0 and less than 14";
      if (stone === 0 && lb === 0) return "Target weight must be greater than 0";
    } else if (!(Number($("ob-target-weight").value) > 0)) {
      return "Enter your target weight in kg";
    }
    return null;
  }
  // units and notifications have no required fields
  return null;
}

function wizardNext() {
  const current = currentWizardStep();
  const idx = WIZARD_STEPS.indexOf(current);
  if (idx === -1 || idx === WIZARD_STEPS.length - 1) return;
  const err = validateWizardStep(current);
  if (err) {
    toast(err);
    return;
  }
  showWizardStep(WIZARD_STEPS[idx + 1]);
}

function wizardBack() {
  const current = currentWizardStep();
  const idx = WIZARD_STEPS.indexOf(current);
  if (idx > 0) showWizardStep(WIZARD_STEPS[idx - 1]);
}

function onWizardFinish() {
  const current = currentWizardStep();
  if (current !== "notifications") return;
  const err = validateWizardStep(current);
  if (err) {
    toast(err);
    return;
  }
  submitOnboarding();
}

function onWizardSubmit(ev) {
  ev.preventDefault();
  // Enter in a step field advances to the next step; on the last step it
  // finishes (mirrors the Continue/Finish buttons).
  if (currentWizardStep() === "notifications") {
    onWizardFinish();
    return;
  }
  wizardNext();
}

/* Unit-mode toggles for the wizard inputs. The hidden-required toggle mirrors
 * the settings forms: a hidden required input makes the browser refuse a
 * submit with a cryptic "not focusable" error. */
function syncWizardHeightUnitUi() {
  const ftIn = checkedRadio("ob-height-unit") === "ft-in";
  $("ob-height-cm").hidden = ftIn;
  $("ob-height-ft-in").hidden = !ftIn;
  $("ob-height-cm").required = !ftIn;
  $("ob-height-ft").required = ftIn;
  $("ob-height-in").required = ftIn;
}

function syncWizardWeightUnitUi() {
  const stLb = checkedRadio("ob-weight-unit") === "st-lb";
  $("ob-weight-kg").hidden = stLb;
  $("ob-weight-st-lb").hidden = !stLb;
  $("ob-weight-kg").required = !stLb;
  $("ob-weight-stone").required = stLb;
  $("ob-weight-lb").required = stLb;
}

function syncWizardTargetUnitUi() {
  const stLb = checkedRadio("ob-target-unit") === "st-lb";
  $("ob-target-weight").hidden = stLb;
  $("ob-target-st-lb").hidden = !stLb;
  $("ob-target-weight").required = !stLb;
  $("ob-target-stone").required = stLb;
  $("ob-target-lb").required = stLb;
}

function syncWizardTargetModeUi() {
  const bmiMode = checkedRadio("ob-target-mode") === "bmi";
  $("ob-target-weight-fields").hidden = bmiMode;
  $("ob-target-bmi-fields").hidden = !bmiMode;
}

/* Live hint on the target step: the derived kg in BMI mode and the
 * under/overweight flag use the SAME arithmetic as the server (format.js
 * mirrors units.py), so what the wizard shows matches the summary's
 * healthy_min_kg/healthy_max_kg/target_status after completion. */
function updateWizardRangeHint() {
  const heightCm = wizardHeightCm();
  const range = healthyRange(heightCm);
  const hintEl = $("ob-range-hint");
  const derivedEl = $("ob-bmi-derived");
  if (range == null) {
    hintEl.hidden = true;
    derivedEl.textContent = "";
    return;
  }
  let targetKg = null;
  let status = null;
  if (checkedRadio("ob-target-mode") === "bmi") {
    const bmiRaw = $("ob-target-bmi").value.trim();
    if (bmiRaw !== "") {
      const bmi = Number(bmiRaw);
      targetKg = weightKgFromBmi(bmi, heightCm);
      status = classifyBmi(bmi);
      derivedEl.textContent = `≈ ${fmt1(targetKg)} kg`;
    } else {
      derivedEl.textContent = "";
    }
  } else {
    targetKg = wizardTargetKg();
    status = targetKg != null ? classifyBmi(bmiFromKg(targetKg, heightCm)) : null;
  }
  const hint = targetRangeHint(targetKg, range[0], range[1], status);
  if (hint) {
    hintEl.textContent = hint.message;
    hintEl.classList.toggle("target-out-of-range", hint.outOfRange);
    hintEl.hidden = false;
  } else {
    hintEl.hidden = true;
  }
}

async function submitOnboarding() {
  const payload = {
    height_cm: wizardHeightCm(),
    weight_kg: wizardWeightKg(),
    weight_unit: unitPref(checkedRadio("ob-weight-unit"), "kg"),
    height_unit: unitPref(checkedRadio("ob-height-unit"), "cm"),
    target_unit: unitPref(checkedRadio("ob-target-unit"), "kg"),
    weight_display: unitPref(checkedRadio("ob-weight-display"), "lb"),
    tip_time: $("ob-tip-time").value.trim(),
    reminder_time: $("ob-reminder-time").value.trim(),
    reminder_weekday: Number($("ob-reminder-weekday").value),
    exercise_time: $("ob-exercise-time").value.trim(),
    primary_goal: wizardPrimaryGoal(),
    secondary_goals: checkedValues("ob-secondary-goals"),
    health_domains: checkedValues("ob-health-domains"),
    activity_level: wizardActivityLevel(),
  };
  if (checkedRadio("ob-target-mode") === "bmi") {
    payload.target_bmi = Number($("ob-target-bmi").value);
  } else {
    payload.target_weight = wizardTargetKg();
  }
  try {
    await fetchJson("/api/onboarding", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("Welcome! Your tracker is set up");
    onboardingScreen.hidden = true;
    showTracker();
    await loadData();
  } catch (err) {
    toast(`Setup failed: ${err.message}`);
  }
}

/* ---- data -------------------------------------------------------------- */

// Cached API payloads the charts redraw from when the Journey tab becomes
// visible (the canvases have zero width while their panel is hidden, so the
// charts are drawn on visibility, not just at load time).
let chartData = { weightEntries: [], weightSummary: null, exerciseEntries: [], mealEntries: [], rewards: null };

// Last earned-checkpoint count seen by loadData. null until the first load
// so the first render is always suppressed (design §Confetti).
let prevEarned = null;

// Last earned-achievement key set from a SUCCESSFUL read. null until the first
// fulfilled /api/achievements response, so the first render never celebrates;
// only re-stored on success, so a failed read cannot reset the diff (design
// §Celebration).
let prevAchievementKeys = null;

// Celebration read-diff state (S6): null until the first successful read.
let prevLevel = null;
let pendingLevelUp = null;
let prevQuestStatus = null;
// Last World island stage from a SUCCESSFUL render. null until the first
// fulfilled /api/xp render, so the first render never celebrates; only
// re-stored after a successful render, so a failed read cannot reset the
// stage-up diff (design §SPA; spec 'Stage-Up Celebration').
let prevWorldStage = null;

// Last earned-collectible key set from a SUCCESSFUL read (null until the
// first fulfilled read); only re-stored on success so a failed read cannot
// reset the first-earn diff (spec 'Collectible First-Earn Signal').
let prevCollectibleKeys = null;

// Collectible first-earn signal seam (spec 'Collectible First-Earn Signal'):
// newly earned keys since the previous successful read queue as minimal
// pending signals for the S6 queue; S5 never consumes or celebrates them.
let collectibleSignals = [];

async function loadData() {
  const [weight, rewards, settings, me, exercise, meals, streaks] = await Promise.all([
    fetchJson("/api/weight"),
    fetchJson("/api/rewards"),
    fetchJson("/api/settings"),
    fetchJson("/api/auth/me"),
    fetchJson("/api/exercise"),
    fetchJson("/api/meals"),
    fetchJson("/api/streaks"),
  ]);
  chartData.weightEntries = weight.entries;
  chartData.weightSummary = weight.summary;
  chartData.exerciseEntries = exercise.entries;
  chartData.mealEntries = meals.entries;
  chartData.rewards = rewards;
  displayUnit = unitPref(settings.weight_display, "lb");
  // Server theme wins post-login (design §JS Theming Lifecycle): resolve the
  // persisted three-state pref to a concrete theme and apply it — this
  // overwrites any pre-auth localStorage choice from the FOUC bootstrap.
  themePref = unitPref(settings.theme, "system");
  applyTheme(resolveTheme(themePref, systemPref()));
  renderSummary(weight.summary);
  renderGoalRing(chartData.weightSummary);
  renderHistory(weight.entries);
  drawChart(chartData.weightEntries, chartData.weightSummary);
  drawExerciseChart(chartData.exerciseEntries);
  drawMealChart(chartData.mealEntries);
  renderRewards(rewards);
  // Confetti eligibility: fire only when the earned checkpoint count rose
  // since the previous load; the first render (prevEarned === null) is
  // always suppressed (design §Confetti).
  if (shouldCelebrate(prevEarned, rewards.earned_count) === "fire") {
    fireConfetti();
  }
  prevEarned = rewards.earned_count;
  renderSettings(settings, me);
  renderExerciseHistory(exercise.entries);
  renderMealHistory(meals.entries);
  renderStreaks(streaks);
  // S4a payloads feed both Today (quests card + chip) and the Journey cards;
  // the journey momentum fetch is separate and failure-scoped (S4b).
  const r1 = await loadQuestsAndXp();
  await loadJourneyCards(r1.quests, r1.xp);
  // Any reload lands back on Today.
  switchTab("today");
}

/* ---- summary ----------------------------------------------------------- */

const SUMMARY_ROWS = [
  ["current", "Current weight"],
  ["baseline", "Starting weight"],
  ["target", "Target weight"],
  ["lost", "Weight lost"],
  ["remaining", "To target"],
];

function renderSummary(s) {
  const grid = $("summary-stats");
  grid.innerHTML = "";
  for (const [key, label] of SUMMARY_ROWS) {
    const stat = document.createElement("div");
    stat.className = "stat";
    const name = document.createElement("div");
    name.className = "stat-label";
    name.textContent = label;
    const value = document.createElement("div");
    value.className = "stat-value";
    // kg only — short enough to stay on one line on a phone, so the heading
    // and the imperial/BMI lines below never force a wrap.
    value.textContent = `${fmt1(s[`${key}_kg`])} kg`;
    stat.append(name, value);
    // Imperial form sits on its own sub-line; only render it when the API
    // supplied an lb value (real stats always do, fresh accounts have null).
    if (s[`${key}_lb`] != null) {
      const imp = document.createElement("div");
      imp.className = "stat-sub";
      imp.textContent = weightImperial(s[`${key}_lb`], s[`${key}_stone`], s[`${key}_stone_lb`], displayUnit);
      stat.append(imp);
    }
    // *_bmi is always present on real weights (baseline/current/target) but
    // null when height is unset; render the line so the spec's "BMI —"
    // shows instead of nothing. Deltas (lost/remaining) never carry a bmi key.
    if (s[`${key}_bmi`] !== undefined) {
      const bmi = document.createElement("div");
      bmi.className = "stat-sub";
      bmi.textContent = `BMI ${bmiLabel(s[`${key}_bmi`])}`;
      stat.append(bmi);
    }
    grid.append(stat);
  }
}

/* ---- history ----------------------------------------------------------- */

/* ---- goal ring --------------------------------------------------------- */

/* Hero goal-progress ring inside #summary-card (design §Ring SVG math; spec
 * 'Goal Progress Ring'): an inline SVG whose progress arc is stroke-dasharray
 * = C = 2πr with stroke-dashoffset = C·(1−pct), so the arc fills pct of the
 * ring (C ≈ 376.991 for r=60). pct comes from the goalProgress mirror helper:
 * null (no loss goal / missing inputs) renders the empty state with helper
 * copy and NO progress circle. The stroke paints url(#goalGrad), whose stops
 * are token-driven in style.css — no chart hex here. The center overlay shows
 * the rounded pct plus the remaining-to-target copy via summary.remaining_*.
 * Empty summaries (fresh accounts) land in the pct==null branch: overlay
 * renders "—" + helper copy, no arc, so the card never breaks. */
function renderGoalRing(summary) {
  const host = $("goal-ring");
  if (!host) return;
  const pct = goalProgress(summary.baseline_kg, summary.current_kg, summary.target_kg);
  const C = 2 * Math.PI * 60; // circumference of the r=60 ring
  const hasGoal = pct != null;
  const arc = hasGoal
    ? `<circle class="goal-ring-progress" cx="70" cy="70" r="60" fill="none" stroke="url(#goalGrad)" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct)}"/>`
    : "";
  const pctText = hasGoal ? `${Math.round(pct * 100)}%` : "—";
  const remainingText = hasGoal
    ? (() => {
        const imp = weightImperial(summary.remaining_lb, summary.remaining_stone, summary.remaining_stone_lb, displayUnit);
        return imp ? `${imp} left` : `${fmt1(summary.remaining_kg)} kg left`;
      })()
    : "Set a target weight to start tracking.";
  host.innerHTML = `
    <svg viewBox="0 0 140 140" class="goal-ring-svg" aria-hidden="true">
      <defs>
        <linearGradient id="goalGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" class="goal-grad-from"/>
          <stop offset="1" class="goal-grad-to"/>
        </linearGradient>
      </defs>
      <circle class="goal-ring-track" cx="70" cy="70" r="60" fill="none"/>
      ${arc}
    </svg>
    <div class="goal-ring-overlay">
      <div class="goal-ring-pct">${pctText}</div>
      <div class="goal-ring-remaining">${remainingText}</div>
    </div>`;
}

function renderHistory(entries) {
  const list = $("entry-list");
  list.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No entries yet — log your first weight above.";
    list.append(empty);
    return;
  }
  for (const e of entries) {
    const li = document.createElement("li");
    li.className = "entry-row";
    const date = document.createElement("span");
    date.className = "entry-date";
    date.textContent = formatDate(e.date);
    const weight = document.createElement("span");
    weight.className = "entry-weight";
    weight.textContent = weightLabel(e.weight_kg, e.lb, e.stone, e.stone_lb, displayUnit);
    const bmi = document.createElement("span");
    bmi.className = "entry-bmi";
    bmi.textContent = `BMI ${bmiLabel(e.bmi)}`;
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "entry-edit-btn";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => editWeightRow(li, e));
    const del = document.createElement("button");
    del.type = "button";
    del.className = "entry-delete";
    del.textContent = "×";
    del.title = "Delete entry";
    del.addEventListener("click", () => deleteEntry(e.id));
    li.append(date);
    if (e.time) {
      const time = document.createElement("span");
      time.className = "entry-time";
      time.textContent = e.time;
      li.append(time);
    }
    li.append(weight, bmi, edit, del);
    list.append(li);
  }
}

async function deleteEntry(id) {
  try {
    await fetchJson(`/api/weight/${id}`, { method: "DELETE" });
    toast("Entry deleted");
    await loadData();
  } catch (err) {
    toast(`Delete failed: ${err.message}`);
  }
}

function editWeightRow(li, entry) {
  li.replaceChildren();
  const form = document.createElement("form");
  form.className = "entry-edit";
  const date = document.createElement("input");
  date.type = "date";
  date.value = entry.date;
  const time = document.createElement("input");
  time.type = "time";
  time.value = entry.time || "";
  const unit = document.createElement("select");
  for (const value of ["kg", "st-lb"]) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    unit.append(opt);
  }
  unit.value = checkedRadio("weight-unit");
  const kg = document.createElement("input");
  kg.type = "number";
  kg.step = "any";
  kg.value = entry.weight_kg;
  // Prefill from the API's derived stone/lb view; stone is whole, lb may be
  // fractional (the exact remainder), so step="any" keeps the browser from
  // blocking submit on a step mismatch.
  const stone = document.createElement("input");
  stone.type = "number";
  stone.step = "any";
  stone.value = entry.stone;
  const lb = document.createElement("input");
  lb.type = "number";
  lb.step = "any";
  // Prefill with the display-rounded value (fmt1) rather than the raw
  // remainder: the server computes stone_lb as a float (e.g. 82.5 kg ->
  // 1.4999999999999998), and the history list hides that with fmt1.
  lb.value = entry.stone_lb != null ? fmt1(entry.stone_lb) : "";
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "Save";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => loadData());
  // Same hidden-field rule as syncWeightUnitUi: toggle required so the hidden
  // input never blocks submit with a "not focusable" validation error.
  const sync = () => {
    const stLb = unit.value === "st-lb";
    kg.hidden = stLb;
    stone.hidden = !stLb;
    lb.hidden = !stLb;
    kg.required = !stLb;
    stone.required = stLb;
    lb.required = stLb;
  };
  unit.addEventListener("change", sync);
  sync();
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    let weightKg;
    if (unit.value === "st-lb") {
      weightKg = stoneLbToKg(Number(stone.value), Number(lb.value));
    } else {
      weightKg = Number(kg.value);
    }
    saveWeight(entry.id, { date: date.value, time: time.value || null, weight_kg: weightKg });
  });
  form.append(date, time, unit, kg, stone, lb, save, cancel);
  li.append(form);
}

async function saveWeight(id, payload) {
  try {
    await fetchJson(`/api/weight/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("Weight updated");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

/* ---- activity: exercise & meals ----------------------------------------- */

function renderExerciseHistory(entries) {
  const list = $("exercise-list");
  list.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No exercise logged yet.";
    list.append(empty);
    return;
  }
  for (const e of entries) {
    const li = document.createElement("li");
    li.className = "entry-row";
    const date = document.createElement("span");
    date.className = "entry-date";
    date.textContent = formatDate(e.date);
    if (e.time) {
      const time = document.createElement("span");
      time.className = "entry-time";
      time.textContent = e.time;
      li.append(time);
    }
    const type = document.createElement("span");
    type.className = "entry-type";
    type.textContent = e.exercise_type;
    const duration = document.createElement("span");
    duration.className = "entry-duration";
    duration.textContent = `${e.duration_min} min`;
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "entry-edit-btn";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => editExerciseRow(li, e));
    const del = document.createElement("button");
    del.type = "button";
    del.className = "entry-delete";
    del.textContent = "×";
    del.title = "Delete entry";
    del.addEventListener("click", () => deleteExercise(e.id));
    li.append(date, type, duration, edit, del);
    list.append(li);
  }
}

function editExerciseRow(li, entry) {
  li.replaceChildren();
  const form = document.createElement("form");
  form.className = "entry-edit";
  const date = document.createElement("input");
  date.type = "date";
  date.value = entry.date;
  const time = document.createElement("input");
  time.type = "time";
  time.value = entry.time || "";
  const select = document.createElement("select");
  for (const t of EXERCISE_TYPES) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    select.append(opt);
  }
  select.value = entry.exercise_type;
  const duration = document.createElement("input");
  duration.type = "number";
  duration.min = "1";
  duration.step = "1";
  duration.value = entry.duration_min;
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "Save";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => loadData());
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    saveExercise(entry.id, {
      date: date.value,
      time: time.value || null,
      exercise_type: select.value,
      duration_min: Number(duration.value),
    });
  });
  form.append(date, time, select, duration, save, cancel);
  li.append(form);
}

async function saveExercise(id, payload) {
  try {
    await fetchJson(`/api/exercise/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("Exercise updated");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

function renderMealHistory(entries) {
  const list = $("meal-list");
  list.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No meals logged yet.";
    list.append(empty);
    return;
  }
  for (const e of entries) {
    const li = document.createElement("li");
    li.className = "entry-row";
    const date = document.createElement("span");
    date.className = "entry-date";
    date.textContent = formatDate(e.date);
    if (e.time) {
      const time = document.createElement("span");
      time.className = "entry-time";
      time.textContent = e.time;
      li.append(time);
    }
    const calories = document.createElement("span");
    calories.className = "entry-calories";
    calories.textContent = `${fmt1(e.calories)} kcal`;
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "entry-edit-btn";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => editMealRow(li, e));
    const del = document.createElement("button");
    del.type = "button";
    del.className = "entry-delete";
    del.textContent = "×";
    del.title = "Delete entry";
    del.addEventListener("click", () => deleteMeal(e.id));
    li.append(date, calories, edit, del);
    list.append(li);
  }
}

function editMealRow(li, entry) {
  li.replaceChildren();
  const form = document.createElement("form");
  form.className = "entry-edit";
  const date = document.createElement("input");
  date.type = "date";
  date.value = entry.date;
  const time = document.createElement("input");
  time.type = "time";
  time.value = entry.time || "";
  const calories = document.createElement("input");
  calories.type = "number";
  calories.min = "1";
  calories.step = "any";
  calories.value = entry.calories;
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "Save";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => loadData());
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    saveMeal(entry.id, {
      date: date.value,
      time: time.value || null,
      calories: Number(calories.value),
    });
  });
  form.append(date, time, calories, save, cancel);
  li.append(form);
}

async function saveMeal(id, payload) {
  try {
    await fetchJson(`/api/meals/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("Meal updated");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

async function deleteExercise(id) {
  try {
    await fetchJson(`/api/exercise/${id}`, { method: "DELETE" });
    toast("Exercise deleted");
    await loadData();
  } catch (err) {
    toast(`Delete failed: ${err.message}`);
  }
}

async function deleteMeal(id) {
  try {
    await fetchJson(`/api/meals/${id}`, { method: "DELETE" });
    toast("Meal deleted");
    await loadData();
  } catch (err) {
    toast(`Delete failed: ${err.message}`);
  }
}

function populateExerciseTypes() {
  const select = $("exercise-type");
  select.innerHTML = "";
  for (const t of EXERCISE_TYPES) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    select.append(opt);
  }
}

async function addExercise(ev) {
  ev.preventDefault();
  const date = $("exercise-date").value || todayLocal();
  const durationMin = Number($("exercise-duration").value);
  const time = $("exercise-time").value || null;
  try {
    await fetchJson("/api/exercise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        date,
        exercise_type: $("exercise-type").value,
        duration_min: durationMin,
        time,
      }),
    });
    $("exercise-duration").value = "";
    $("exercise-time").value = "";
    toast("Exercise saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

async function addMeal(ev) {
  ev.preventDefault();
  const date = $("meal-date").value || todayLocal();
  const calories = Number($("meal-calories").value);
  const time = $("meal-time").value || null;
  try {
    await fetchJson("/api/meals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, calories, time }),
    });
    $("meal-calories").value = "";
    $("meal-time").value = "";
    toast("Meal saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

/* ---- streaks ------------------------------------------------------------ */

const STREAK_TILES = [
  ["weight_weeks", "Weight streak", "weeks"],
  ["exercise_weeks", "Exercise streak", "weeks"],
  ["meal_days", "Meal streak", "days"],
];

function renderStreaks(s) {
  const grid = $("streak-stats");
  grid.innerHTML = "";
  for (const [key, label, unit] of STREAK_TILES) {
    const tile = document.createElement("div");
    tile.className = "stat streak-tile";
    // Active-streak data attribute gates the flame pulse (Phase 3); the
    // flame itself renders for every tile, styled by .flame.
    tile.dataset.streakActive = String(s[key] > 0);
    const flame = document.createElement("span");
    flame.className = "flame";
    flame.textContent = "🔥";
    const value = document.createElement("div");
    value.className = "stat-value";
    value.textContent = String(s[key]);
    const unitEl = document.createElement("div");
    unitEl.className = "stat-unit";
    unitEl.textContent = unit;
    const name = document.createElement("div");
    name.className = "stat-label";
    name.textContent = label;
    tile.append(flame, value, unitEl, name);
    grid.append(tile);
  }
}

/* ---- chart ------------------------------------------------------------- */

/* Token-driven chart palette: read ONCE from the computed styles so the
 * canvases follow the design tokens instead of hardcoded hex (design
 * §Component Styling Plan). The computed body font keeps the system-ui
 * fallback while Baloo 2 loads. */
const chartStyle = getComputedStyle(document.documentElement);
const chartFontFamily = getComputedStyle(document.body).fontFamily || "system-ui, sans-serif";
const CHART_COLORS = {
  line: chartStyle.getPropertyValue("--accent").trim(),
  grid: chartStyle.getPropertyValue("--border").trim(),
  muted: chartStyle.getPropertyValue("--muted").trim(),
  tooltip: chartStyle.getPropertyValue("--text").trim(),
  tooltipText: chartStyle.getPropertyValue("--card").trim(),
};
const CHART_FONT = `11px ${chartFontFamily}`;
const CHART_FONT_LARGE = `14px ${chartFontFamily}`;

/* Dark-mode theme lifecycle (design §JS Theming Lifecycle): a three-state
 * preference (system|light|dark) resolves to a concrete light/dark theme.
 * The preference is tracked here so the prefers-color-scheme listener can
 * be added only in "system" mode and removed otherwise (design D5). */
let themePref = "system";
const themeQuery = window.matchMedia("(prefers-color-scheme: dark)");
let themeSystemHandler = null;

function systemPref() {
  return themeQuery.matches ? "dark" : "light";
}

function refreshChartColors() {
  const cs = getComputedStyle(document.documentElement);
  CHART_COLORS.line = cs.getPropertyValue("--accent").trim();
  CHART_COLORS.grid = cs.getPropertyValue("--border").trim();
  CHART_COLORS.muted = cs.getPropertyValue("--muted").trim();
  CHART_COLORS.tooltip = cs.getPropertyValue("--text").trim();
  CHART_COLORS.tooltipText = cs.getPropertyValue("--card").trim();
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
  refreshChartColors();
  // Redraw only what is visible: hidden panels re-render on switchTab (design
  // 'Redraw only when visible').
  if (!$("tab-journey").hidden) {
    drawChart(chartData.weightEntries, chartData.weightSummary);
    drawExerciseChart(chartData.exerciseEntries);
    drawMealChart(chartData.mealEntries);
  }
  syncThemeSystemListener();
}

/* D5: the OS color-scheme listener exists ONLY in "system" mode; every
 * applyTheme (called on load + every pref change) re-syncs it, so the
 * listener never drifts after a mode switch. The stored handler ref lets us
 * remove the exact same listener we added. */
function syncThemeSystemListener() {
  if (themePref === "system") {
    if (themeSystemHandler == null) {
      themeSystemHandler = () => applyTheme(resolveTheme("system", systemPref()));
      themeQuery.addEventListener("change", themeSystemHandler);
    }
  } else if (themeSystemHandler != null) {
    themeQuery.removeEventListener("change", themeSystemHandler);
    themeSystemHandler = null;
  }
}

function drawChart(entries, summary) {
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.clientWidth;
  canvas.height = 260;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!entries.length) {
    ctx.fillStyle = CHART_COLORS.muted;
    ctx.font = CHART_FONT_LARGE;
    ctx.textAlign = "center";
    ctx.fillText("Log entries to see your progress chart", canvas.width / 2, canvas.height / 2);
    return;
  }

  const pad = { top: 16, right: 16, bottom: 28, left: 44 };
  const w = canvas.width - pad.left - pad.right;
  const h = canvas.height - pad.top - pad.bottom;
  // The API returns entries newest-first (the history list shows them that
  // way); the chart reads left -> right in time, so plot a reversed copy —
  // oldest on the left, newest on the right. Every coordinate below follows
  // this chronological array.
  const points = chronological(entries);
  const kgs = points.map((e) => e.weight_kg);
  const min = Math.min(...kgs) - 1;
  const max = Math.max(...kgs) + 1;
  const xAt = (i) => pad.left + (points.length === 1 ? w / 2 : (i / (points.length - 1)) * w);
  const yAt = (v) => pad.top + h - ((v - min) / (max - min)) * h;

  // grid lines
  ctx.strokeStyle = CHART_COLORS.grid;
  ctx.fillStyle = CHART_COLORS.muted;
  ctx.font = CHART_FONT;
  ctx.textAlign = "right";
  for (let g = 0; g <= 4; g++) {
    const v = min + ((max - min) / 4) * g;
    const y = yAt(v);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(canvas.width - pad.right, y);
    ctx.stroke();
    ctx.fillText(fmt1(v), pad.left - 6, y + 4);
  }

  // line + points
  ctx.strokeStyle = CHART_COLORS.line;
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((e, i) => (i === 0 ? ctx.moveTo(xAt(i), yAt(e.weight_kg)) : ctx.lineTo(xAt(i), yAt(e.weight_kg))));
  ctx.stroke();

  ctx.fillStyle = CHART_COLORS.line;
  for (const [i, e] of points.entries()) {
    ctx.beginPath();
    ctx.arc(xAt(i), yAt(e.weight_kg), 3.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // x labels (sparse). First label is left-aligned and the last is
  // right-aligned so a "DD/MM/YY" never clips outside the canvas; the rest
  // stay centered.
  const step = Math.max(1, Math.ceil(points.length / 6));
  for (let i = 0; i < points.length; i += step) {
    const x = xAt(i);
    if (i === 0) {
      ctx.textAlign = "left";
    } else if (i + step >= points.length) {
      ctx.textAlign = "right";
    } else {
      ctx.textAlign = "center";
    }
    ctx.fillText(formatDate(points[i].date), x, canvas.height - 8);
  }

  // tooltip
  canvas.onmousemove = (ev) => {
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    let nearest = 0;
    let best = Infinity;
    points.forEach((e, i) => {
      const d = Math.abs(xAt(i) - mx);
      if (d < best) {
        best = d;
        nearest = i;
      }
    });
    if (best > w / points.length) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    drawChart(entries, summary);
    const e = points[nearest];
    const label = `${formatDate(e.date)}\n${weightLabel(e.weight_kg, e.lb, e.stone, e.stone_lb, displayUnit)}\nBMI ${bmiLabel(e.bmi)}`;
    const box = { x: xAt(nearest) + 10, y: Math.max(pad.top, yAt(e.weight_kg) - 30), w: 0, h: 0 };
    ctx.font = CHART_FONT;
    const lines = label.split("\n");
    ctx.textAlign = "left";
    const lineH = 14;
    box.w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 12;
    box.h = lines.length * lineH + 10;
    if (box.x + box.w > canvas.width - 4) box.x = xAt(nearest) - box.w - 10;
    ctx.fillStyle = CHART_COLORS.tooltip;
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.fillStyle = CHART_COLORS.tooltipText;
    lines.forEach((l, i) => ctx.fillText(l, box.x + 6, box.y + 14 + i * lineH));
  };
  canvas.onmouseleave = () => drawChart(entries, summary);
}

/* ---- tabs ---------------------------------------------------------------- */

function switchTab(name) {
  for (const btn of document.querySelectorAll(".tab-btn")) {
    const active = btn.dataset.tab === name;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  }
  for (const panel of document.querySelectorAll(".tab-panel")) {
    panel.hidden = panel.id !== `tab-${name}`;
  }
  // The canvases have zero width while their panel is hidden, so the charts
  // are drawn here, on visibility, from the cached data — not only at load.
  if (name === "journey") {
    drawChart(chartData.weightEntries, chartData.weightSummary);
    drawExerciseChart(chartData.exerciseEntries);
    drawMealChart(chartData.mealEntries);
  }
}

/* ---- activity charts ------------------------------------------------------ */

function drawExerciseChart(entries) {
  const canvas = $("chart-exercise");
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.clientWidth;
  canvas.height = 260;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const weeks = exerciseMinutesPerWeek(entries);
  if (!weeks.length) {
    ctx.fillStyle = CHART_COLORS.muted;
    ctx.font = CHART_FONT_LARGE;
    ctx.textAlign = "center";
    ctx.fillText("Log exercise to see your weekly chart", canvas.width / 2, canvas.height / 2);
    return;
  }
  drawBars(canvas, ctx, weeks.map((w) => w.minutes), weeks.map((w) => formatDate(w.weekStart)));
}

function drawMealChart(entries) {
  const canvas = $("chart-meals");
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.clientWidth;
  canvas.height = 260;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const days = caloriesPerDay(entries);
  if (!days.length) {
    ctx.fillStyle = CHART_COLORS.muted;
    ctx.font = CHART_FONT_LARGE;
    ctx.textAlign = "center";
    ctx.fillText("Log meals to see your daily chart", canvas.width / 2, canvas.height / 2);
    return;
  }
  drawBars(canvas, ctx, days.map((d) => d.calories), days.map((d) => formatDate(d.date)));
}

function drawBars(canvas, ctx, values, labels) {
  const pad = { top: 16, right: 16, bottom: 28, left: 44 };
  const w = canvas.width - pad.left - pad.right;
  const h = canvas.height - pad.top - pad.bottom;
  const max = Math.max(...values) || 1;
  const slot = w / values.length;
  const barW = Math.max(2, slot * 0.6);
  const yAt = (v) => pad.top + h - (v / max) * h;

  // grid lines + y labels
  ctx.strokeStyle = CHART_COLORS.grid;
  ctx.fillStyle = CHART_COLORS.muted;
  ctx.font = CHART_FONT;
  ctx.textAlign = "right";
  for (let g = 0; g <= 4; g++) {
    const v = (max / 4) * g;
    const y = yAt(v);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(canvas.width - pad.right, y);
    ctx.stroke();
    ctx.fillText(fmt1(v), pad.left - 6, y + 4);
  }

  // bars
  ctx.fillStyle = CHART_COLORS.line;
  values.forEach((value, i) => {
    const x = pad.left + i * slot + (slot - barW) / 2;
    ctx.fillRect(x, yAt(value), barW, pad.top + h - yAt(value));
  });

  // x labels (sparse)
  ctx.textAlign = "center";
  const step = Math.max(1, Math.ceil(values.length / 6));
  for (let i = 0; i < values.length; i += step) {
    ctx.fillText(labels[i], pad.left + i * slot + slot / 2, canvas.height - 8);
  }
}

/* ---- rewards ----------------------------------------------------------- */

/* Confetti burst on a newly-earned checkpoint (design §Confetti): decorative
 * non-text fills only, so the AA text rule does not apply (same exemption as
 * --gold). --danger is a fill accent here, never text. */
const CONFETTI_COLORS = ["var(--fox)", "var(--gold)", "var(--accent)", "var(--danger)"];
const CONFETTI_COUNT = 24;

function fireConfetti() {
  // Reduced-motion gate: never spawn pieces for users who opt out (the CSS
  // reduced-motion block hides any strays as well).
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  for (let i = 0; i < CONFETTI_COUNT; i++) {
    const piece = document.createElement("span");
    piece.className = "confetti-piece";
    // Randomized inline vars drive the CSS fall: --x horizontal drift, --rot
    // end rotation, --delay stagger, --color from the token palette.
    piece.style.setProperty("--x", `${(Math.random() * 240 - 120).toFixed(0)}px`);
    piece.style.setProperty("--rot", `${(Math.random() * 540 - 270).toFixed(0)}deg`);
    piece.style.setProperty("--delay", `${(Math.random() * 0.4).toFixed(2)}s`);
    piece.style.setProperty("--color", CONFETTI_COLORS[i % CONFETTI_COLORS.length]);
    piece.style.left = `${20 + Math.random() * 60}%`;
    piece.addEventListener("animationend", () => piece.remove());
    document.body.append(piece);
  }
}

/* Achieved-milestone strip (UI refinement of the five-card grid): ONE line
 * of compact dots, one per ACHIEVED checkpoint in ascending percent order
 * (10->100); the last achieved dot is scaled up with a gold ring; pending
 * milestones are not rendered at all; the next milestone is a text-only line
 * built by milestoneNextLabel (format.js). Threshold labels derive uniformly
 * from kg via kgToImperial -> weightLabel, so the strip and the next line
 * can never diverge. */
const MILESTONE_EMOJI = ["🚶", "🏃", "🔥", "🏆", "🎯"];
const MILESTONE_PERCENTS = [10, 25, 50, 75, 100];

function renderRewards(r) {
  const el = $("rewards-content");
  el.innerHTML = "";
  const earned = document.createElement("p");
  earned.className = "rewards-count";
  earned.textContent = `${r.earned_count} of 5 checkpoints earned`;
  el.append(earned);

  if (r.next_checkpoint) {
    const track = document.createElement("div");
    track.className = "progress-track";
    const fill = document.createElement("div");
    fill.className = "progress-fill";
    const pct = Math.round((r.progress_to_next || 0) * 100);
    fill.style.width = `${pct}%`;
    track.append(fill);
    const pctLabel = document.createElement("div");
    pctLabel.className = "progress-label";
    pctLabel.textContent = `${pct}% of the way to the next checkpoint`;
    el.append(track, pctLabel);
  } else {
    const done = document.createElement("p");
    done.className = "rewards-done";
    done.textContent = "All checkpoints earned — great work! 🎉";
    el.append(done);
  }

  // Thresholds for all five percents from the mirror helper; the baseline
  // rides on the cached weight summary (identical to rewards start_kg by
  // construction — same compute_baseline), the target ships in the payload.
  // No thresholds (no target, or target >= baseline) renders nothing beyond
  // the count/band above — the null-target case preserved from the grid era.
  const thresholds = checkpointThresholds(
    chartData.weightSummary?.baseline_kg ?? null,
    r.target_kg ?? null
  );
  if (thresholds.length === 0) return;

  // One dot per ACHIEVED checkpoint, ascending; pending ones stay out of the
  // DOM. The max-percent dot is the last-achieved highlight.
  const earnedCps = (r.active_checkpoints || [])
    .slice()
    .sort((a, b) => a.percent - b.percent);
  const lastPct = earnedCps.length > 0 ? earnedCps[earnedCps.length - 1].percent : null;

  const strip = document.createElement("div");
  strip.className = "milestone-strip";
  strip.id = "milestone-strip";
  for (const cp of earnedCps) {
    const dot = document.createElement("div");
    const dotClasses = ["milestone-dot", "is-earned"];
    if (cp.percent === lastPct) dotClasses.push("is-last-achieved");
    dot.className = dotClasses.join(" ");
    dot.setAttribute("data-percent", String(cp.percent));
    dot.title = `${cp.percent}% — ${fmt1(cp.threshold_kg)} kg`;
    const emoji = document.createElement("span");
    emoji.className = "milestone-dot-emoji";
    emoji.setAttribute("aria-hidden", "true");
    emoji.textContent =
      MILESTONE_EMOJI[MILESTONE_PERCENTS.indexOf(cp.percent)] ?? "✅";
    const pctLabel = document.createElement("span");
    pctLabel.className = "milestone-dot-pct";
    pctLabel.textContent = `${cp.percent}%`;
    dot.append(emoji, pctLabel);
    strip.append(dot);
  }
  if (earnedCps.length > 0) el.append(strip);

  // Next milestone: text info only, no icon; all five earned -> copy line.
  const next = document.createElement("p");
  next.className = "milestone-next";
  next.textContent = r.next_checkpoint
    ? milestoneNextLabel(
        r.next_checkpoint.percent,
        r.next_checkpoint.threshold_kg,
        displayUnit
      )
    : "All checkpoints earned!";
  el.append(next);
}

/* ---- daily quests + XP chip (r1-quests-xp S4a) ------------------------- */

/* R1 requests are failure-scoped (design §Loading): quests and XP load via
 * Promise.allSettled so one failed fetch shows a scoped error and never
 * blanks the rest of the Today view. Shared by loadData and the post-mutation
 * refresh in mutateQuest. Sequencing matters: /api/quests reconciles (and
 * persists) read-detected completions and /api/xp derives its total from
 * those rows, so the XP fetch must settle AFTER the quests fetch — racing
 * them can render a stale chip total when an auto-completion persists
 * between the two responses. */
async function loadQuestsAndXp() {
  const [questsRes] = await Promise.allSettled([fetchJson("/api/quests")]);
  if (questsRes.status === "fulfilled") {
    renderQuests(questsRes.value);
  } else {
    showQuestsError(questsRes.reason);
  }
  const [xpRes] = await Promise.allSettled([fetchJson("/api/xp")]);
  if (xpRes.status === "fulfilled") {
    renderXpChip(xpRes.value);
    // World island renders from the same successful XP read; stage-up
    // confetti fires only when the stage rose between successful renders,
    // and prevWorldStage updates only after that render/diff (design §SPA).
    const currentStage = renderWorld(xpRes.value);
    if (stageChanged(prevWorldStage, currentStage) === "fire") {
      fireConfetti();
    }
    prevWorldStage = currentStage;
    const level = xpRes.value.level;
    if (prevLevel !== null && level > prevLevel) {
      // Level-up banner (R14): stage on fulfilled read; the mutateQuest
      // marker supplies the precise pre-transition level.
      enqueueCelebrationEvents([{ type: "level_up", from: pendingLevelUp?.to === level ? pendingLevelUp.from : prevLevel, to: level, title: xpRes.value.title }]);
    }
    pendingLevelUp = null;
    prevLevel = level;
  } else {
    const el = $("xp-chip-content");
    el.innerHTML = "";
    const err = document.createElement("p");
    err.className = "hint error";
    err.textContent = "Could not load XP";
    el.append(err);
  }
  return { quests: questsRes.value, xp: xpRes.value };
}

/* ---- journey progress cards (r1-quests-xp S4b) ------------------------- */

/* Journey renders three progression cards from the S4a payloads (quests,
 * XP) plus momentum and weekly objectives, all failure-scoped:
 * loadJourneyCards renders XP and quest history from the already-fetched
 * quests/XP responses and fetches /api/momentum, /api/achievements, and
 * /api/weekly together so one failed Journey request never blanks the others
 * (spec 'Journey Data Loading'). Weekly joins the same allSettled batch so it
 * refreshes after every relevant UI reload (r2-completion S3). */
async function loadJourneyCards(questsPayload, xpPayload) {
  const [momRes, achRes, weeklyRes, collRes] = await Promise.allSettled([
    fetchJson("/api/momentum"),
    fetchJson("/api/achievements"),
    fetchJson("/api/weekly"),
    fetchJson("/api/collectibles"),
  ]);
  renderJourneyXp(xpPayload);
  renderQuestHistory(questsPayload);
  if (momRes.status === "fulfilled") {
    renderMomentum(momRes.value);
  } else {
    const el = $("momentum-card-content");
    el.innerHTML = "";
    const err = document.createElement("p");
    err.className = "hint error";
    err.textContent = "Could not load momentum";
    el.append(err);
  }
  renderAchievements(achRes);
  renderWeekly(weeklyRes);
  renderCollectibles(collRes);
  enqueueCelebrationEvents(drainCelebrationSignals());
  void flushCelebrationQueue();
}

function renderJourneyXp(xp) {
  const el = $("xp-card-content");
  el.innerHTML = "";
  if (!xp) {
    const err = document.createElement("p");
    err.className = "hint error";
    err.textContent = "Could not load XP";
    el.append(err);
    return;
  }
  const title = document.createElement("div");
  title.className = "journey-xp-title";
  title.textContent = xp.title;
  const level = document.createElement("div");
  level.className = "journey-xp-level";
  level.textContent = `Level ${xp.level} · ${xp.total_xp} XP`;
  el.append(title, level);
  // Progress toward the next level (same exact-span math as the chip).
  const span = xp.next_level_at - thresholdForLevel(xp.level);
  const pct =
    span > 0 ? Math.min(100, Math.round((xp.xp_into_next / span) * 100)) : 100;
  const progress = document.createElement("div");
  progress.className = "journey-xp-progress";
  const track = document.createElement("div");
  track.className = "progress-track";
  const fill = document.createElement("div");
  fill.className = "progress-fill";
  fill.style.width = `${pct}%`;
  track.append(fill);
  const label = document.createElement("div");
  label.className = "progress-label";
  label.textContent = `${xp.xp_into_next} / ${span} XP to level ${xp.level + 1}`;
  progress.append(track, label);
  el.append(progress);
  // Recent completions: newest first (the API returns them that way).
  const recent = document.createElement("ul");
  recent.className = "journey-recent";
  for (const c of xp.recent_completions ?? []) {
    const li = document.createElement("li");
    li.className = "journey-recent-row";
    const name = document.createElement("span");
    name.textContent = c.title;
    const awarded = document.createElement("span");
    awarded.className = "journey-recent-xp";
    awarded.textContent = `+${c.xp_value} XP`;
    li.append(name, awarded);
    recent.append(li);
  }
  el.append(recent);
}

function renderMomentum(m) {
  const el = $("momentum-card-content");
  el.innerHTML = "";
  if (!m) return;
  const tier = document.createElement("div");
  tier.className = "momentum-tier";
  tier.textContent = m.today_tier === "none" ? "No momentum yet" : m.today_tier;
  const count = document.createElement("div");
  count.className = "momentum-count";
  count.textContent = `${m.successful_days} successful day${m.successful_days === 1 ? "" : "s"} in the last ${m.window_days}`;
  el.append(tier, count);
}

/* ---- achievements card (r2-achievements S3) ---------------------------- */

function renderAchievements(achRes) {
  const el = $("achievements-card-content");
  el.innerHTML = "";
  if (achRes.status !== "fulfilled") {
    const err = document.createElement("p");
    err.className = "hint error";
    err.textContent = "Could not load achievements";
    el.append(err);
    return;
  }
  const achievements = achRes.value?.achievements ?? [];
  const earned = achievements.filter((a) => a.earned).map((a) => a.key);
  // Read-diff celebration: genuinely new earned keys queue (R16).
  if (prevAchievementKeys !== null) {
    enqueueCelebrationEvents(newAchievementKeys(prevAchievementKeys, earned).map((key) => ({ type: "achievement", key, title: achievements.find((a) => a.key === key)?.title ?? key })));
  }
  prevAchievementKeys = earned;
  const list = document.createElement("ul");
  list.className = "achievement-list";
  for (const a of achievements) {
    const li = document.createElement("li");
    li.className = "achievement-row";
    // data-state hooks the earned/locked rows for tests and styling; locked
    // rows never show partial progress (spec 'Journey Progress Cards').
    li.dataset.state = a.earned ? "earned" : "locked";
    const title = document.createElement("span");
    title.className = "achievement-title";
    title.textContent = a.title;
    const state = document.createElement("span");
    state.className = "achievement-state";
    state.textContent = a.earned ? `Unlocked ${formatDate(a.unlocked_at)}` : "Locked";
    li.append(title, state);
    list.append(li);
  }
  el.append(list);
}

/* ---- collectibles shelf + World accent (r2-completion S5) -------------- */

/* Card-scoped and recovery-safe: a rejected read surfaces the static
 * #collectibles-error while prior shelf rows stay intact; success re-renders
 * the shelf + World accent. */
function renderCollectibles(collRes) {
  const err = $("collectibles-error");
  if (collRes.status !== "fulfilled") {
    err.textContent = "Could not load collectibles";
    err.hidden = false;
    return;
  }
  err.hidden = true;
  const collectibles = collRes.value?.collectibles ?? [];
  const earned = collectibles.filter((c) => c.earned).map((c) => c.key);
  // First-earn diff (S6 seam): only genuinely new keys after a successful
  // read; first render and unchanged/lost sets stay quiet.
  if (prevCollectibleKeys !== null) {
    const fresh = newAchievementKeys(prevCollectibleKeys, earned);
    if (fresh.length > 0) {
      collectibleSignals.push({ type: "collectible_first_earn", keys: fresh, titles: fresh.map((key) => collectibles.find((c) => c.key === key)?.title ?? key) });
    }
  }
  prevCollectibleKeys = earned;
  renderCollectibleShelf(collectibles);
  renderWorldLatestEarn(collectibles);
}

function renderCollectibleShelf(collectibles) {
  const list = $("collectibles-list");
  list.innerHTML = "";
  for (const c of collectibles) {
    const li = document.createElement("li");
    li.className = "collectible-row";
    li.dataset.state = c.earned ? "earned" : "locked";
    li.dataset.key = c.key;
    // CSS-only medallion art (earned) vs muted silhouette (locked); aria-hidden.
    const art = document.createElement("span");
    art.className = "collectible-art";
    art.setAttribute("aria-hidden", "true");
    const title = document.createElement("span");
    title.className = "collectible-title";
    title.textContent = c.title;
    const state = document.createElement("span");
    state.className = "collectible-state";
    state.textContent = c.earned ? `Unlocked ${formatDate(c.unlocked_at)}` : "Locked";
    li.append(art, title, state);
    list.append(li);
  }
}

/* DD/MM/YY -> numeric YYMMDD key (31/07/26 < 05/08/26); unmatched -> 0. */
function ddMmYyKey(dateStr) {
  const m = /^(\d{2})\/(\d{2})\/(\d{2})$/.exec(String(dateStr));
  return m ? Number(m[3] + m[2] + m[1]) : 0;
}

/* World accent (spec R12): most recent earn wins by DD/MM/YY chronology
 * (numeric YYMMDD key); ties keep the earliest catalogue entry. */
function renderWorldLatestEarn(collectibles) {
  const accent = $("world-latest-earn");
  if (!accent) return;
  const earned = collectibles.filter((c) => c.earned && c.unlocked_at != null);
  if (earned.length === 0) {
    accent.setAttribute("hidden", "");
    accent.removeAttribute("data-key");
    accent.setAttribute("aria-label", "");
    return;
  }
  let latest = earned[0];
  for (const c of earned) {
    if (ddMmYyKey(c.unlocked_at) > ddMmYyKey(latest.unlocked_at)) latest = c;
  }
  accent.removeAttribute("hidden");
  accent.dataset.key = latest.key;
  accent.setAttribute("aria-label", `Latest collectible: ${latest.title}`);
}

function renderQuestHistory(questsPayload) {
  const el = $("quest-history-content");
  el.innerHTML = "";
  const history = questsPayload?.history ?? [];
  if (history.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "No quests logged yet — your journey starts today.";
    el.append(empty);
    return;
  }
  const list = document.createElement("ul");
  list.className = "entry-list";
  for (const q of history) {
    const li = document.createElement("li");
    li.className = "quest-history-row";
    // Decorative domain icon leads the row; the domain text supplies the
    // meaning, so the icon is hidden from the accessibility tree (spec
    // 'Quest Icons' R4). Fail-loud unknown domains are intentional.
    const icon = document.createElement("span");
    icon.className = "quest-domain-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = iconForDomain(q.domain);
    const date = document.createElement("span");
    date.className = "quest-history-date";
    date.textContent = formatDate(q.date);
    const name = document.createElement("span");
    name.className = "quest-history-name";
    name.textContent = q.title;
    const status = document.createElement("span");
    status.className = "quest-history-status";
    status.textContent = questStatusLabel(q);
    const awarded = document.createElement("span");
    awarded.className = "quest-history-xp";
    // Non-done statuses award zero XP (spec 'Journey Progress Cards').
    awarded.textContent = q.status === "done" ? `+${q.xp_value} XP` : "0 XP";
    li.append(icon, date, name, status, awarded);
    list.append(li);
  }
  el.append(list);
}

/* ---- weekly objectives (r2-completion S3) ------------------------------ */

/* Weekly-met signal seam (spec 'Weekly-Met Signal'): on every SUCCESSFUL
 * weekly read, each met_flips goal is queued as a minimal pending signal for
 * the S6 celebration queue. S3 never consumes or celebrates it, and there is
 * no replay logic — the server's exactly-once transient met_flips are trusted
 * as-is. */
let weeklyMetSignals = [];

/* Deterministic exemption countdown: next Monday is week_start + 7; the delta
 * derives from the local calendar date, floors at 0, and keeps singular/plural
 * copy (spec 'Weekly Objectives UI'). */
function weeklyDaysUntilMonday(weekStartIso) {
  const nextMonday = new Date(`${weekStartIso}T00:00:00Z`);
  nextMonday.setUTCDate(nextMonday.getUTCDate() + 7);
  const now = new Date();
  const todayUtc = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.max(0, Math.round((nextMonday.getTime() - todayUtc) / 86400000));
}

function weeklyErrorNode() {
  const err = document.createElement("p");
  err.className = "hint error";
  err.setAttribute("role", "alert");
  err.textContent = "Could not load weekly objectives";
  return err;
}

/* Failure is card-scoped and recovery-safe: a failed weekly read shows the
 * static Today #weekly-error slot while the container-first rows stay intact;
 * only the Journey status/history contents are replaced (rebuilt on success). */
function renderWeekly(weeklyRes) {
  const err = $("weekly-error");
  if (weeklyRes.status !== "fulfilled") {
    err.textContent = "Could not load weekly objectives";
    err.hidden = false;
    const status = $("weekly-current-status");
    status.innerHTML = "";
    status.append(weeklyErrorNode());
    const history = $("weekly-history");
    if (history) history.innerHTML = "";
    return;
  }
  err.hidden = true;
  const data = weeklyRes.value;
  // S6 signal seam: met_flips only from a successful read (the queue is not
  // consumed by S3).
  for (const goal of data.met_flips ?? []) {
    weeklyMetSignals.push({ type: "weekly_met", goal });
  }
  renderWeeklyToday(data);
  renderWeeklyJourney(data);
}

function renderWeeklyToday(data) {
  const exempt = $("weekly-exempt");
  if (data.current?.exempt) {
    const days = weeklyDaysUntilMonday(data.current.week_start);
    exempt.textContent = `Exempt this week - starts Monday in ${days} day${days === 1 ? "" : "s"}`;
    exempt.hidden = false;
  } else {
    exempt.textContent = "";
    exempt.hidden = true;
  }
  for (const goal of data.current?.goals ?? []) {
    const row = document.querySelector(`#weekly-content .weekly-progress-row[data-goal="${goal.goal}"]`);
    if (!row) continue;
    row.dataset.met = goal.met ? "true" : "false";
    const count = row.querySelector(".weekly-progress-count");
    if (count) count.textContent = `${goal.current} / ${goal.target}`;
    const status = row.querySelector(".weekly-progress-status");
    if (status) status.textContent = goal.met ? "Met" : `${goal.current} / ${goal.target}`;
    const track = row.querySelector(".progress-track");
    if (track) {
      track.setAttribute("role", "progressbar");
      track.setAttribute("aria-valuemin", "0");
      track.setAttribute("aria-valuemax", String(goal.target));
      track.setAttribute("aria-valuenow", String(goal.current));
    }
    const fill = row.querySelector(".progress-fill");
    if (fill) {
      const pct =
        goal.target > 0
          ? Math.min(100, Math.max(0, Math.round((goal.current / goal.target) * 100)))
          : 0;
      fill.style.width = `${pct}%`;
    }
  }
}

function renderWeeklyJourney(data) {
  const statusEl = $("weekly-current-status");
  const historyEl = $("weekly-history");
  statusEl.innerHTML = "";
  historyEl.innerHTML = "";
  const exempt = Boolean(data.current?.exempt);
  if (exempt) {
    const days = weeklyDaysUntilMonday(data.current.week_start);
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = `Exempt this week - starts Monday in ${days} day${days === 1 ? "" : "s"}`;
    statusEl.append(note);
  }
  const statusList = document.createElement("ul");
  statusList.className = "weekly-status-list";
  for (const goal of data.current?.goals ?? []) {
    const li = document.createElement("li");
    li.className = "weekly-status-row";
    li.dataset.goal = goal.goal;
    li.dataset.met = goal.met ? "true" : "false";
    const name = document.createElement("span");
    name.className = "weekly-status-name";
    name.textContent = goal.goal === "quests" ? "Quests" : "Good days";
    const state = document.createElement("span");
    state.className = "weekly-status-state";
    // Exempt overrides the per-goal state text so a partial week can never be
    // misread as awarded/met; the countdown stays visible above (spec 'Weekly
    // Objectives UI').
    state.textContent = exempt ? "Exempt" : goal.met ? "Met" : `${goal.current} / ${goal.target}`;
    li.append(name, state);
    statusList.append(li);
  }
  statusEl.append(statusList);

  // History stays newest-first: the API returns it that way, but the copy is
  // defensively re-sorted descending by week_start so render order never
  // depends on server order (spec 'Weekly Objectives UI').
  const history = [...(data.history ?? [])].sort((a, b) =>
    a.week_start < b.week_start ? 1 : a.week_start > b.week_start ? -1 : 0
  );
  if (history.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "No completed weeks yet.";
    historyEl.append(empty);
    return;
  }
  const list = document.createElement("ul");
  list.className = "weekly-history-list";
  for (const week of history) {
    const li = document.createElement("li");
    li.className = "weekly-history-row";
    const date = document.createElement("span");
    date.className = "weekly-history-date";
    date.textContent = formatDate(week.week_start);
    const goals = document.createElement("span");
    goals.className = "weekly-history-goals";
    goals.textContent = week.exempt
      ? "Exempt"
      : week.goals
          .map((g) => `${g.goal === "quests" ? "Quests" : "Good days"}: ${g.met ? "Met" : "Not met"}`)
          .join(" \u00b7 ");
    li.append(date, goals);
    list.append(li);
  }
  historyEl.append(list);
}

function showQuestsError(err) {
  const errorEl = $("quests-error");
  errorEl.textContent = `Could not load quests: ${err.message}`;
  errorEl.hidden = false;
}

/* The row's status text: detected completion must read as auto-completed,
 * manual completion as done, skipped stays skipped, open stays open. */
function questStatusLabel(q) {
  if (q.status === "done") {
    return q.source === "detected" ? "Auto-completed" : "Done";
  }
  if (q.status === "skipped") return "Skipped";
  return "Open";
}

function renderQuests(data) {
  const list = $("quests-list");
  list.innerHTML = "";
  for (const q of data.quests) {
    const row = document.createElement("li");
    row.className = "quest-row";
    row.dataset.questId = String(q.id);
    row.dataset.status = q.status;
    const label = document.createElement("div");
    label.className = "quest-title";
    // Decorative domain icon leads the title; the domain text supplies the
    // meaning, so the icon is hidden from the accessibility tree (spec
    // 'Quest Icons' R4). Fail-loud unknown domains are intentional.
    const icon = document.createElement("span");
    icon.className = "quest-domain-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = iconForDomain(q.domain);
    label.textContent = q.title;
    label.prepend(icon);
    const meta = document.createElement("div");
    meta.className = "quest-meta";
    const domain = document.createElement("span");
    domain.className = "quest-domain";
    domain.textContent = q.domain;
    const xp = document.createElement("span");
    xp.className = "quest-xp";
    xp.textContent = `+${q.xp_value} XP`;
    meta.append(domain, xp);
    const status = document.createElement("div");
    status.className = "quest-status";
    if (q.status === "done") status.classList.add("is-done");
    status.textContent = questStatusLabel(q);
    row.append(label, meta, status);
    // Open rows offer Complete/Skip/Replace; terminal (done/skipped) rows
    // expose no invalid controls.
    if (q.status === "open") {
      row.append(buildQuestActions(q.id));
    }
    list.append(row);
  }
  enqueueCelebrationEvents(questStatusChanged(prevQuestStatus, data.quests).map((d) => ({ type: "quest_delight", questId: d.questId })));
  prevQuestStatus = data.quests.map((q) => ({ id: q.id, status: q.status }));
}

function buildQuestActions(questId) {
  const actions = document.createElement("div");
  actions.className = "quest-actions";
  for (const [action, label] of [
    ["complete", "Complete"],
    ["skip", "Skip"],
    ["replace", "Replace"],
  ]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "quest-action";
    btn.dataset.action = action;
    btn.dataset.questId = String(questId);
    btn.textContent = label;
    actions.append(btn);
  }
  return actions;
}

/* Mutation flow: disable every quest action while a request is pending (no
 * duplicate submission), announce success or failure without ever removing
 * the card, and on success re-fetch quests + XP so the completed row
 * refreshes to done and the chip reflects the new total. A rejected second
 * replacement (409) leaves the rendered assignment unchanged and surfaces
 * the server detail in the accessible error region. */
async function mutateQuest(questId, action) {
  const card = $("quests-card");
  const errorEl = $("quests-error");
  for (const btn of card.querySelectorAll(".quest-action")) btn.disabled = true;
  errorEl.hidden = true;
  try {
    const res = await fetchJson(`/api/quests/${questId}/${action}`, {
      method: "POST",
    });
    // mutateQuest POST reports a level crossing; consumed by the next
    // successful XP read so a failed read cannot lose it.
    if (res.level_up) pendingLevelUp = { from: res.level_up.from, to: res.level_up.to };
    const r1 = await loadQuestsAndXp();
    await loadJourneyCards(r1.quests, r1.xp);
  } catch (err) {
    errorEl.textContent = `Could not ${action} quest: ${err.message}`;
    errorEl.hidden = false;
  } finally {
    for (const btn of card.querySelectorAll(".quest-action")) btn.disabled = false;
  }
}

/* ---- check-in (mood scale + habit quick-log) -----------------------------
 * The Today check-in card posts a mood (1-5, optional note) or a habit type
 * to the shipped endpoints, then refreshes quests + XP so an assigned
 * mood_checkin/habit_checkin flips to Auto-completed on the next read.
 * Mirrors the quest-action mutation pattern: disable controls while pending,
 * keep the user's selection/note on failure, clear only after success.
 * Habit chips render from the pinned HABIT_TYPES literal (drift-guard), with
 * human labels from WeightFormat.habitLabel; mood values are guarded
 * client-side by validateMood before any fetch (empty/0/6/non-integer). */

function renderHabitChips() {
  const row = $("habit-chips");
  row.innerHTML = "";
  for (const type of HABIT_TYPES) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "checkin-habit";
    chip.dataset.habitType = type;
    chip.textContent = habitLabel(type);
    row.append(chip);
  }
}

function selectedMood() {
  const btn = document.querySelector('.checkin-mood[aria-pressed="true"]');
  return btn ? Number(btn.dataset.mood) : null;
}

function setMoodPending(pending) {
  for (const btn of document.querySelectorAll(".checkin-mood")) btn.disabled = pending;
  // Success clears the selection, so the submit button returns to disabled;
  // failure preserves it, so the button comes back enabled.
  $("mood-submit").disabled = pending || selectedMood() === null;
}

/* Per-element success-hint timers: each hint owns its hide timer, so a mood
 * success and a habit success within 3s of each other hide independently — a
 * shared timer would let the first message stay visible forever. */
const _checkinSuccessTimers = new Map();

function showCheckinSuccess(id, message) {
  const el = $(id);
  el.textContent = message;
  el.hidden = false;
  const prev = _checkinSuccessTimers.get(id);
  if (prev) clearTimeout(prev);
  _checkinSuccessTimers.set(id, setTimeout(() => {
    el.hidden = true;
    _checkinSuccessTimers.delete(id);
  }, 3000));
}

function hideCheckinSuccess(id) {
  const el = $(id);
  el.hidden = true;
  const timer = _checkinSuccessTimers.get(id);
  if (timer) {
    clearTimeout(timer);
    _checkinSuccessTimers.delete(id);
  }
}

async function submitMood(ev) {
  ev.preventDefault();
  const mood = selectedMood();
  const note = $("mood-note").value.trim();
  const errorEl = $("mood-error");
  errorEl.hidden = true;
  hideCheckinSuccess("mood-success");
  if (mood === null || !validateMood(mood)) {
    errorEl.textContent = "Choose a mood from 1 to 5.";
    errorEl.hidden = false;
    return;
  }
  setMoodPending(true);
  try {
    const payload = { mood };
    if (note) payload.note = note;
    await fetchJson("/api/mood", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    // Success: clear the selection and note, then refresh quests + XP so an
    // assigned mood_checkin flips to Auto-completed (source "detected").
    for (const btn of document.querySelectorAll(".checkin-mood")) btn.setAttribute("aria-pressed", "false");
    $("mood-note").value = "";
    $("mood-submit").disabled = true;
    showCheckinSuccess("mood-success", "Mood logged. Quests refreshed.");
    await loadQuestsAndXp();
  } catch (err) {
    errorEl.textContent = `Could not log mood: ${err.message}`;
    errorEl.hidden = false;
  } finally {
    setMoodPending(false);
  }
}

async function logHabit(habitType) {
  if (!HABIT_TYPES.includes(habitType)) return;
  const chips = document.querySelectorAll(".checkin-habit");
  const errorEl = $("habit-error");
  errorEl.hidden = true;
  hideCheckinSuccess("habit-success");
  for (const chip of chips) chip.disabled = true;
  try {
    await fetchJson("/api/habits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ habit_type: habitType }),
    });
    // Success: quick-log needs no form state; refresh quests + XP so an
    // assigned habit_checkin flips to Auto-completed on the next read.
    showCheckinSuccess("habit-success", "Habit logged. Quests refreshed.");
    await loadQuestsAndXp();
  } catch (err) {
    errorEl.textContent = `Could not log habit: ${err.message}`;
    errorEl.hidden = false;
  } finally {
    for (const chip of chips) chip.disabled = false;
  }
}

function renderXpChip(xp) {
  const el = $("xp-chip-content");
  el.innerHTML = "";
  const title = document.createElement("div");
  title.className = "xp-chip-title";
  title.textContent = xp.title;
  const level = document.createElement("div");
  level.className = "xp-chip-level";
  level.textContent = `Level ${xp.level}`;
  const total = document.createElement("div");
  total.className = "xp-chip-total";
  total.textContent = `${xp.total_xp} XP`;
  el.append(title, level, total);
  // Progress toward the next level: xp_into_next of the level's span
  // (next_level_at - T(level)) — the threshold mirror keeps the denominator
  // exact, and the label names the absolute next_level_at target.
  const span = xp.next_level_at - thresholdForLevel(xp.level);
  const pct =
    span > 0 ? Math.min(100, Math.round((xp.xp_into_next / span) * 100)) : 100;
  const progress = document.createElement("div");
  progress.className = "xp-chip-progress";
  const track = document.createElement("div");
  track.className = "progress-track";
  const fill = document.createElement("div");
  fill.className = "progress-fill";
  fill.style.width = `${pct}%`;
  track.append(fill);
  const label = document.createElement("div");
  label.className = "progress-label";
  label.textContent = `${xp.xp_into_next} / ${span} XP to level ${xp.level + 1}`;
  progress.append(track, label);
  el.append(progress);
}

/* World island live render (r2-world-xp-island S3): derives the current
 * stage from the fetched /api/xp payload via the format.js worldStage mirror
 * and drives the static S2 island — #world-card data-stage, #world-island
 * data-current-stage + aria-label, the stage name, and the scoped progress
 * fill/label. Stage 1 labels the level span; stages 2-4 normalize progress
 * across the stage bands (0/700/2700/10450/23200); stage 5 is terminal.
 * Returns the rendered stage so the caller can evaluate stageChanged(). */
const WORLD_STAGE_NAMES = [
  "Sprout Isle",
  "Explorer Isle",
  "Adventurer Isle",
  "Champion Isle",
  "Legend Isle",
];
const WORLD_STAGE_STARTS = [700, 2700, 10450, 23200];

function renderWorld(xp) {
  const currentStage = worldStage(xp.total_xp);
  $("world-card").dataset.stage = String(currentStage);
  const island = $("world-island");
  island.dataset.currentStage = String(currentStage);
  island.setAttribute(
    "aria-label",
    `Your XP island, stage ${currentStage}, ${WORLD_STAGE_NAMES[currentStage - 1]}`
  );
  $("world-stage-name").textContent = WORLD_STAGE_NAMES[currentStage - 1];
  const fill = $("world-progress").querySelector(".progress-fill");
  const label = $("world-progress").querySelector(".progress-label");
  if (currentStage === 5) {
    label.textContent = "Island fully evolved";
    fill.style.width = "100%";
  } else if (currentStage === 1) {
    const span = xp.next_level_at - thresholdForLevel(xp.level);
    const pct =
      span > 0 ? Math.min(100, Math.round((xp.xp_into_next / span) * 100)) : 100;
    label.textContent = `${xp.xp_into_next} / ${span}`;
    fill.style.width = `${pct}%`;
  } else {
    const start = WORLD_STAGE_STARTS[currentStage - 2];
    const next = WORLD_STAGE_STARTS[currentStage - 1];
    const pct = Math.max(
      0,
      Math.min(100, Math.round(((xp.total_xp - start) / (next - start)) * 100))
    );
    label.textContent = `${xp.total_xp - start} / ${next - start}`;
    fill.style.width = `${pct}%`;
  }
  return currentStage;
}

/* ---- settings ---------------------------------------------------------- */

function setRadio(name, value) {
  const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (el) el.checked = true;
}

function renderSettings(s, me) {
  $("account-email").value = me?.email ?? "";
  $("target-weight").value = s.target_weight ?? "";
  $("height-cm").value = s.height_cm ?? "";
  $("tip-time").value = s.tip_time ?? "";
  $("reminder-time").value = s.reminder_time ?? "";
  $("reminder-weekday").value = s.reminder_weekday ?? 0;
  $("exercise-time").value = s.exercise_time ?? "";
  $("start-override").value = s.start_weight_override ?? "";
  // Per-user input units: each radio group opens in the saved preference
  // (kg / cm by default).
  setRadio("weight-unit", unitPref(s.weight_unit, "kg"));
  setRadio("height-unit", unitPref(s.height_unit, "cm"));
  setRadio("target-unit", unitPref(s.target_unit, "kg"));
  setRadio("weight-display", unitPref(s.weight_display, "lb"));
  // Appearance radio mirrors the same theme preference as the header toggle
  // (design §JS Theming Lifecycle): system/light/dark, default "system".
  setRadio("appearance", unitPref(s.theme, "system"));
  renderGoalsLifestyle(s);
  syncWeightUnitUi();
  syncHeightUnitUi();
  syncTargetUnitUi();
  renderGoalRangeHint();
}

/* Goals & lifestyle settings card (spec user-onboarding): prefill the Me
 * selects and check the persisted list values. The lists are free-form on
 * the backend, so a saved value outside the preset options is simply left
 * unchecked rather than dropped on the next save. */
function renderGoalsLifestyle(s) {
  $("primary-goal").value = s.primary_goal ?? "";
  $("activity-level").value = s.activity_level ?? "";
  const secondary = new Set(s.secondary_goals ?? []);
  for (const el of document.querySelectorAll('input[name="secondary-goals"]')) {
    el.checked = secondary.has(el.value);
  }
  const domains = new Set(s.health_domains ?? []);
  for (const el of document.querySelectorAll('input[name="health-domains"]')) {
    el.checked = domains.has(el.value);
  }
}

/* Healthy-range flag under the Goal & body form: reuses the summary's
 * healthy_min_kg/healthy_max_kg/target_status (weight-tracking spec keys) via
 * the same targetRangeHint helper the wizard uses. */
function renderGoalRangeHint() {
  const summary = chartData.weightSummary;
  const hint = targetRangeHint(
    summary?.target_kg ?? null,
    summary?.healthy_min_kg ?? null,
    summary?.healthy_max_kg ?? null,
    summary?.target_status ?? null
  );
  const el = $("goal-range-hint");
  if (!hint) {
    el.hidden = true;
    return;
  }
  el.textContent = hint.message;
  el.classList.toggle("target-out-of-range", hint.outOfRange);
  el.hidden = false;
}

const num = (id) => {
  const v = $(id).value.trim();
  return v === "" ? null : Number(v);
};
const time = (id) => {
  // Empty input disables the schedule (the "" sentinel); never null,
  // which would remove the override and restore the default instead.
  return $(id).value.trim();
};

async function saveAccount(ev) {
  ev.preventDefault();
  const email = $("account-email").value.trim();
  if (!email) return;
  try {
    await fetchJson("/api/auth/me", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    toast("Email saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

async function saveGoal(ev) {
  ev.preventDefault();
  let heightCm;
  if (checkedRadio("height-unit") === "ft-in") {
    const ftRaw = $("height-ft").value.trim();
    const inRaw = $("height-in").value.trim();
    if (ftRaw === "" && inRaw === "") {
      heightCm = null; // height unset, same as an empty cm field
    } else if (ftRaw === "" || inRaw === "") {
      toast("Enter both feet and inches, or leave both empty to unset height");
      return;
    } else {
      const ft = Number(ftRaw);
      const inches = Number(inRaw);
      if (!(ft >= 0)) {
        toast("Feet must be 0 or more");
        return;
      }
      if (!(inches >= 0) || inches >= 12) {
        toast("Inches must be at least 0 and less than 12");
        return;
      }
      heightCm = ftInToCm(ft, inches);
    }
  } else {
    heightCm = num("height-cm");
  }
  let targetKg;
  if (checkedRadio("target-unit") === "st-lb") {
    const stoneRaw = $("target-stone").value.trim();
    const lbRaw = $("target-lb").value.trim();
    if (stoneRaw === "" || lbRaw === "") {
      toast("Enter both stone and pounds for the target");
      return;
    }
    const stone = Number(stoneRaw);
    const lb = Number(lbRaw);
    if (!Number.isInteger(stone) || stone < 0) {
      toast("Target stone must be a whole number, 0 or more");
      return;
    }
    if (!(lb >= 0) || lb >= 14) {
      toast("Target pounds must be at least 0 and less than 14");
      return;
    }
    if (stone === 0 && lb === 0) {
      toast("Target weight must be greater than 0");
      return;
    }
    targetKg = stoneLbToKg(stone, lb);
  } else {
    targetKg = num("target-weight");
  }
  try {
    await fetchJson("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_weight: targetKg,
        height_cm: heightCm,
        start_weight_override: num("start-override"),
      }),
    });
    toast("Goal saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

async function saveGoalsLifestyle(ev) {
  ev.preventDefault();
  try {
    await fetchJson("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        primary_goal: $("primary-goal").value.trim() || null,
        secondary_goals: checkedValues("secondary-goals"),
        health_domains: checkedValues("health-domains"),
        activity_level: $("activity-level").value.trim() || null,
      }),
    });
    toast("Goals saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

async function saveReminders(ev) {
  ev.preventDefault();
  try {
    await fetchJson("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tip_time: time("tip-time"),
        reminder_time: time("reminder-time"),
        reminder_weekday: Number($("reminder-weekday").value),
        exercise_time: time("exercise-time"),
      }),
    });
    toast("Reminders saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

/* ---- entries ----------------------------------------------------------- */

function todayLocal() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

async function addEntry(ev) {
  ev.preventDefault();
  const date = $("entry-date").value || todayLocal();
  let weightKg;
  if (checkedRadio("weight-unit") === "st-lb") {
    const stoneRaw = $("entry-stone").value.trim();
    const lbRaw = $("entry-lb").value.trim();
    if (stoneRaw === "" || lbRaw === "") {
      toast("Enter both stone and pounds");
      return;
    }
    const stone = Number(stoneRaw);
    const lb = Number(lbRaw);
    if (!Number.isInteger(stone) || stone < 0) {
      toast("Stone must be a whole number, 0 or more");
      return;
    }
    if (!(lb >= 0) || lb >= 14) {
      toast("Pounds must be at least 0 and less than 14");
      return;
    }
    if (stone === 0 && lb === 0) {
      toast("Weight must be greater than 0");
      return;
    }
    weightKg = stoneLbToKg(stone, lb);
  } else {
    weightKg = Number($("entry-weight").value);
  }
  try {
    await fetchJson("/api/weight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, weight_kg: weightKg, time: $("entry-time").value || null }),
    });
    $("entry-weight").value = "";
    $("entry-time").value = "";
    toast("Entry saved");
    await loadData();
  } catch (err) {
    toast(`Save failed: ${err.message}`);
  }
}

/* ---- push notifications ------------------------------------------------ */

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

async function enablePush() {
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      throw new Error("Push notifications are not supported in this browser");
    }
    const reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
    const { public_key: publicKey } = await fetchJson("/api/push/vapid-public-key");
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
    await fetchJson("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: sub.endpoint,
        p256dh: btoa(String.fromCharCode(...new Uint8Array(sub.getKey("p256dh")))),
        auth: btoa(String.fromCharCode(...new Uint8Array(sub.getKey("auth")))),
      }),
    });
    toast("Notifications enabled");
    setPushUi(true);
  } catch (err) {
    toast(`Could not enable notifications: ${err.message}`);
  }
}

async function disablePush() {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) {
      setPushUi(false);
      toast("Notifications are already off");
      return;
    }
    await fetchJson("/api/push/unsubscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: sub.endpoint }),
    });
    await sub.unsubscribe();
    toast("Notifications disabled");
    setPushUi(false);
  } catch (err) {
    toast(`Could not disable notifications: ${err.message}`);
  }
}

async function testPush() {
  try {
    const res = await fetchJson("/api/push/test", { method: "POST" });
    toast(`Test notification sent to ${res.sent} device${res.sent === 1 ? "" : "s"}`);
  } catch (err) {
    toast(`Test failed: ${err.message}`);
  }
}

function setPushUi(enabled) {
  $("enable-push").hidden = enabled;
  $("disable-push").hidden = !enabled;
  $("test-push").hidden = !enabled;
}

async function restorePushUi() {
  // On a fresh page load the buttons default to "not enabled"; check the
  // real subscription so an already-enabled device stays showing Disable/Test
  // instead of flipping back to Enable after every refresh.
  try {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setPushUi(false);
      return;
    }
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    setPushUi(!!sub);
  } catch (_) {
    /* push stays optional; keep the Enable button */
    setPushUi(false);
  }
}

/* ---- init -------------------------------------------------------------- */

function checkedRadio(name) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value || "";
}

function syncWeightUnitUi() {
  const stLb = checkedRadio("weight-unit") === "st-lb";
  $("entry-weight").hidden = stLb;
  $("entry-st-lb").hidden = !stLb;
  // Toggle required so the hidden field never blocks submit (a hidden
  // required input makes the browser refuse to submit the form with a
  // cryptic "invalid form control is not focusable" error).
  $("entry-weight").required = !stLb;
  $("entry-stone").required = stLb;
  $("entry-lb").required = stLb;
}

function syncHeightUnitUi() {
  const ftIn = checkedRadio("height-unit") === "ft-in";
  $("height-cm").hidden = ftIn;
  $("height-ft-in").hidden = !ftIn;
  // Toggle required so the hidden cm field never blocks submit (same
  // hidden-required pitfall as the weight unit).
  $("height-cm").required = !ftIn;
  $("height-ft").required = ftIn;
  $("height-in").required = ftIn;
}

function syncTargetUnitUi() {
  const stLb = checkedRadio("target-unit") === "st-lb";
  $("target-weight").hidden = stLb;
  $("target-st-lb").hidden = !stLb;
  $("target-weight").required = !stLb;
  $("target-stone").required = stLb;
  $("target-lb").required = stLb;
}

let _unitSaveTimer = null;

function currentWeightDisplay() {
  const checked = document.querySelector('input[name="weight-display"]:checked');
  return checked ? checked.value : displayUnit;
}

function refreshWeightLabels() {
  renderSummary(chartData.weightSummary);
  renderHistory(chartData.weightEntries);
  if (chartData.rewards) renderRewards(chartData.rewards);
  drawChart(chartData.weightEntries, chartData.weightSummary);
}

async function saveUnitPreference() {
  // Changing the weight/height unit anywhere is a preference change: persist
  // it immediately (debounced) so a reload keeps the chosen format. A failed
  // save is silent — the on-screen toggle already updated the UI.
  clearTimeout(_unitSaveTimer);
  _unitSaveTimer = setTimeout(async () => {
    try {
      await fetchJson("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          weight_unit: checkedRadio("weight-unit"),
          height_unit: checkedRadio("height-unit"),
          target_unit: checkedRadio("target-unit"),
          weight_display: currentWeightDisplay(),
        }),
      });
    } catch (_) {
      /* preference save is best-effort */
    }
  }, 300);
}

/* ---- theme preference (design §JS Theming Lifecycle) ------------------- */

let _themeSaveTimer = null;

function nextThemePref(pref) {
  // Header toggle cycles system -> light -> dark -> system (task 5.4). The
  // Settings radio sets the pref directly; both persist via the same PUT.
  if (pref === "system") return "light";
  if (pref === "light") return "dark";
  return "system";
}

async function saveThemePreference() {
  // Theme changes are preference changes: persist immediately (debounced) so
  // a reload keeps the choice; a failed save is silent — the DOM already
  // updated. Mirrors saveUnitPreference.
  clearTimeout(_themeSaveTimer);
  _themeSaveTimer = setTimeout(async () => {
    try {
      await fetchJson("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme: themePref }),
      });
    } catch (_) {
      /* preference save is best-effort */
    }
  }, 300);
}

function onThemeToggle() {
  themePref = nextThemePref(themePref);
  applyTheme(resolveTheme(themePref, systemPref()));
  saveThemePreference();
}

async function init() {
  authForm.addEventListener("submit", submitAuth);
  $("auth-toggle").addEventListener("click", () =>
    setAuthMode(authMode === "signup" ? "login" : "signup")
  );
  $("forgot-link").addEventListener("click", showForgotForm);
  $("forgot-back").addEventListener("click", showAuthForm);
  $("forgot-form").addEventListener("submit", submitForgot);
  $("reset-form").addEventListener("submit", submitReset);
  $("logout-btn").addEventListener("click", logout);
  $("theme-toggle").addEventListener("click", onThemeToggle);
  for (const btn of document.querySelectorAll(".tab-btn")) {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  }
  $("entry-form").addEventListener("submit", addEntry);
  $("exercise-form").addEventListener("submit", addExercise);
  $("meal-form").addEventListener("submit", addMeal);
  $("account-form").addEventListener("submit", saveAccount);
  $("goal-form").addEventListener("submit", saveGoal);
  $("goals-lifestyle-settings-form").addEventListener("submit", saveGoalsLifestyle);
  $("reminders-form").addEventListener("submit", saveReminders);
  $("quests-list").addEventListener("click", (ev) => {
    const btn = ev.target.closest(".quest-action");
    if (!btn) return;
    mutateQuest(btn.dataset.questId, btn.dataset.action);
  });
  renderHabitChips();
  $("mood-form").addEventListener("submit", submitMood);
  $("mood-checkin").addEventListener("click", (ev) => {
    const btn = ev.target.closest(".checkin-mood");
    if (!btn || btn.disabled) return;
    for (const b of document.querySelectorAll(".checkin-mood")) {
      b.setAttribute("aria-pressed", b === btn ? "true" : "false");
    }
    $("mood-submit").disabled = false;
    $("mood-error").hidden = true;
    hideCheckinSuccess("mood-success");
  });
  $("habit-chips").addEventListener("click", (ev) => {
    const chip = ev.target.closest(".checkin-habit");
    if (!chip || chip.disabled) return;
    logHabit(chip.dataset.habitType);
  });
  $("enable-push").addEventListener("click", enablePush);
  $("disable-push").addEventListener("click", disablePush);
  $("test-push").addEventListener("click", testPush);
  $("entry-date").value = todayLocal();
  $("exercise-date").value = todayLocal();
  $("meal-date").value = todayLocal();
  populateExerciseTypes();
  for (const r of document.querySelectorAll('input[name="weight-unit"]')) {
    r.addEventListener("change", () => {
      syncWeightUnitUi();
      saveUnitPreference();
    });
  }
  for (const r of document.querySelectorAll('input[name="height-unit"]')) {
    r.addEventListener("change", () => {
      syncHeightUnitUi();
      saveUnitPreference();
    });
  }
  for (const r of document.querySelectorAll('input[name="target-unit"]')) {
    r.addEventListener("change", () => {
      syncTargetUnitUi();
      saveUnitPreference();
    });
  }
  for (const r of document.querySelectorAll('input[name="weight-display"]')) {
    r.addEventListener("change", () => {
      displayUnit = r.value;
      refreshWeightLabels();
      saveUnitPreference();
    });
  }
  for (const r of document.querySelectorAll('input[name="appearance"]')) {
    r.addEventListener("change", () => {
      themePref = r.value;
      applyTheme(resolveTheme(themePref, systemPref()));
      saveThemePreference();
    });
  }
  $("onboarding-form").addEventListener("submit", onWizardSubmit);
  for (const btn of document.querySelectorAll(".wizard-step [data-action]")) {
    btn.addEventListener("click", () => {
      if (btn.dataset.action === "next") wizardNext();
      else if (btn.dataset.action === "back") wizardBack();
      else if (btn.dataset.action === "finish") onWizardFinish();
    });
  }
  for (const r of document.querySelectorAll('input[name="ob-height-unit"]')) {
    r.addEventListener("change", () => {
      syncWizardHeightUnitUi();
      updateWizardRangeHint();
    });
  }
  for (const r of document.querySelectorAll('input[name="ob-weight-unit"]')) {
    r.addEventListener("change", syncWizardWeightUnitUi);
  }
  for (const r of document.querySelectorAll('input[name="ob-target-unit"]')) {
    r.addEventListener("change", () => {
      syncWizardTargetUnitUi();
      updateWizardRangeHint();
    });
  }
  for (const r of document.querySelectorAll('input[name="ob-target-mode"]')) {
    r.addEventListener("change", () => {
      syncWizardTargetModeUi();
      updateWizardRangeHint();
    });
  }
  for (const id of ["ob-target-weight", "ob-target-stone", "ob-target-lb", "ob-target-bmi"]) {
    $(id).addEventListener("input", updateWizardRangeHint);
  }
  syncWizardHeightUnitUi();
  syncWizardWeightUnitUi();
  syncWizardTargetUnitUi();
  syncWizardTargetModeUi();
  syncWeightUnitUi();
  syncHeightUnitUi();
  syncTargetUnitUi();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* push stays optional */
    });
  }

  // A password-reset link (?reset=<token>) deep-links straight to the reset
  // form; strip the token from the URL so it is not left in the address bar.
  const params = new URLSearchParams(location.search);
  const reset = params.get("reset");
  if (reset) {
    resetToken = reset;
    history.replaceState(null, "", location.pathname);
  }

  let authenticated = false;
  let me = null;
  try {
    me = await fetchJson("/api/auth/me");
    authenticated = true;
  } catch (_) {
    /* 401 (or a network error) leaves the gate visible. No scary toast on a
       fresh visit — the auth form surfaces errors when the user submits. */
  }
  if (authenticated) {
    if (enterApp(me)) {
      try {
        await loadData();
      } catch (err) {
        toast(`Could not load data: ${err.message}`);
      }
      await restorePushUi();
    }
    // else: needs_onboarding — the wizard is showing and tracker data stays
    // hidden until the user completes it (submitOnboarding handles the rest).
  } else if (resetToken) {
    showResetForm();
  }
}

init();
