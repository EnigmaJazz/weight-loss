/* Weight Loss Tracker — vanilla JS SPA.
 * Formats the API's raw values (kg + lb + stone + BMI) for display.
 * Rounding to one decimal is done here, never in the API. */
"use strict";

const $ = (id) => document.getElementById(id);
const toastEl = $("toast");

/* ---- formatting -------------------------------------------------------- */
/* fmt1/weightLabel/summaryLabel live in static/format.js (index.html loads it
 * before app.js) so node:test can pin the exact display contract. */
const { fmt1, weightLabel, summaryLabel, stoneLbToKg, ftInToCm } = globalThis.WeightFormat;
const {
  normalizeUsername,
  validateUsername,
  validatePassword,
  normalizeEmail,
  validateEmail,
} = globalThis.AuthForm;

function bmiLabel(bmi) {
  return bmi == null ? "—" : fmt1(bmi);
}

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (toastEl.hidden = true), 3000);
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
  trackerEl.hidden = true;
  $("logout-btn").hidden = true;
  showAuthForm();
}

function showTracker() {
  authScreen.hidden = true;
  trackerEl.hidden = false;
  $("logout-btn").hidden = false;
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
    showTracker();
    await loadData();
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

/* ---- data -------------------------------------------------------------- */

async function loadData() {
  const [weight, rewards, settings, me] = await Promise.all([
    fetchJson("/api/weight"),
    fetchJson("/api/rewards"),
    fetchJson("/api/settings"),
    fetchJson("/api/auth/me"),
  ]);
  renderSummary(weight.summary);
  renderHistory(weight.entries);
  drawChart(weight.entries, weight.summary);
  renderRewards(rewards);
  renderSettings(settings, me);
}

/* ---- summary ----------------------------------------------------------- */

const SUMMARY_ROWS = [
  ["current", "Current"],
  ["baseline", "Baseline"],
  ["target", "Target"],
  ["lost", "Lost"],
  ["remaining", "Remaining"],
];

function renderSummary(s) {
  const grid = $("summary-stats");
  grid.innerHTML = "";
  for (const [key, label] of SUMMARY_ROWS) {
    const stat = document.createElement("div");
    stat.className = "stat";
    const value = document.createElement("div");
    value.className = "stat-value";
    value.textContent = summaryLabel(s, key);
    const name = document.createElement("div");
    name.className = "stat-label";
    name.textContent = label;
    stat.append(value, name);
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
    date.textContent = e.date;
    const weight = document.createElement("span");
    weight.className = "entry-weight";
    weight.textContent = weightLabel(e.weight_kg, e.lb, e.stone, e.stone_lb);
    const bmi = document.createElement("span");
    bmi.className = "entry-bmi";
    bmi.textContent = `BMI ${bmiLabel(e.bmi)}`;
    const del = document.createElement("button");
    del.type = "button";
    del.className = "entry-delete";
    del.textContent = "×";
    del.title = "Delete entry";
    del.addEventListener("click", () => deleteEntry(e.id));
    li.append(date, weight, bmi, del);
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

/* ---- chart ------------------------------------------------------------- */

function drawChart(entries, summary) {
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.clientWidth;
  canvas.height = 260;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!entries.length) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "14px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Log entries to see your progress chart", canvas.width / 2, canvas.height / 2);
    return;
  }

  const pad = { top: 16, right: 16, bottom: 28, left: 44 };
  const w = canvas.width - pad.left - pad.right;
  const h = canvas.height - pad.top - pad.bottom;
  const kgs = entries.map((e) => e.weight_kg);
  const min = Math.min(...kgs) - 1;
  const max = Math.max(...kgs) + 1;
  const xAt = (i) => pad.left + (entries.length === 1 ? w / 2 : (i / (entries.length - 1)) * w);
  const yAt = (v) => pad.top + h - ((v - min) / (max - min)) * h;

  // grid lines
  ctx.strokeStyle = "#e2e8f0";
  ctx.fillStyle = "#94a3b8";
  ctx.font = "11px system-ui, sans-serif";
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
  ctx.strokeStyle = "#2f7d54";
  ctx.lineWidth = 2;
  ctx.beginPath();
  entries.forEach((e, i) => (i === 0 ? ctx.moveTo(xAt(i), yAt(e.weight_kg)) : ctx.lineTo(xAt(i), yAt(e.weight_kg))));
  ctx.stroke();

  ctx.fillStyle = "#2f7d54";
  for (const [i, e] of entries.entries()) {
    ctx.beginPath();
    ctx.arc(xAt(i), yAt(e.weight_kg), 3.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // x labels (sparse)
  ctx.textAlign = "center";
  const step = Math.max(1, Math.ceil(entries.length / 6));
  for (let i = 0; i < entries.length; i += step) {
    ctx.fillText(entries[i].date.slice(5), xAt(i), canvas.height - 8);
  }

  // tooltip
  canvas.onmousemove = (ev) => {
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    let nearest = 0;
    let best = Infinity;
    entries.forEach((e, i) => {
      const d = Math.abs(xAt(i) - mx);
      if (d < best) {
        best = d;
        nearest = i;
      }
    });
    if (best > w / entries.length) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    drawChart(entries, summary);
    const e = entries[nearest];
    const label = `${e.date}\n${weightLabel(e.weight_kg, e.lb, e.stone, e.stone_lb)}\nBMI ${bmiLabel(e.bmi)}`;
    const box = { x: xAt(nearest) + 10, y: Math.max(pad.top, yAt(e.weight_kg) - 30), w: 0, h: 0 };
    ctx.font = "11px system-ui, sans-serif";
    const lines = label.split("\n");
    ctx.textAlign = "left";
    const lineH = 14;
    box.w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 12;
    box.h = lines.length * lineH + 10;
    if (box.x + box.w > canvas.width - 4) box.x = xAt(nearest) - box.w - 10;
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.fillStyle = "#f8fafc";
    lines.forEach((l, i) => ctx.fillText(l, box.x + 6, box.y + 14 + i * lineH));
  };
  canvas.onmouseleave = () => drawChart(entries, summary);
}

/* ---- rewards ----------------------------------------------------------- */

function renderRewards(r) {
  const el = $("rewards-content");
  el.innerHTML = "";
  const earned = document.createElement("p");
  earned.className = "rewards-count";
  earned.textContent = `${r.earned_count} of 5 checkpoints earned`;
  el.append(earned);

  if (r.next_checkpoint) {
    const nxt = r.next_checkpoint;
    const row = document.createElement("p");
    row.className = "rewards-next";
    row.textContent = `Next checkpoint (${nxt.percent}%): ${weightLabel(nxt.threshold_kg, nxt.threshold_lb, nxt.threshold_stone, nxt.threshold_stone_lb)}`;
    el.append(row);

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

  if (r.active_checkpoints.length) {
    const list = document.createElement("ul");
    list.className = "checkpoint-list";
    for (const cp of r.active_checkpoints) {
      const li = document.createElement("li");
      const badge = document.createElement("span");
      badge.className = "checkpoint-badge";
      badge.textContent = `${cp.percent}%`;
      const label = document.createElement("span");
      label.className = "checkpoint-label";
      label.textContent = weightLabel(cp.threshold_kg, cp.threshold_lb, cp.threshold_stone, cp.threshold_stone_lb);
      const when = document.createElement("span");
      when.className = "checkpoint-when";
      when.textContent = cp.earned_at ? `earned ${cp.earned_at.slice(0, 10)}` : "pending";
      li.append(badge, label, when);
      list.append(li);
    }
    el.append(list);
  }
}

/* ---- settings ---------------------------------------------------------- */

function renderSettings(s, me) {
  $("account-email").value = me?.email ?? "";
  $("target-weight").value = s.target_weight ?? "";
  $("height-cm").value = s.height_cm ?? "";
  $("tip-time").value = s.tip_time ?? "";
  $("reminder-time").value = s.reminder_time ?? "";
  $("reminder-weekday").value = s.reminder_weekday ?? 0;
  $("exercise-time").value = s.exercise_time ?? "";
  $("start-override").value = s.start_weight_override ?? "";
}

async function saveSettings(ev) {
  ev.preventDefault();
  const num = (id) => {
    const v = $(id).value.trim();
    return v === "" ? null : Number(v);
  };
  const time = (id) => {
    // Empty input disables the schedule (the "" sentinel); never null,
    // which would remove the override and restore the default instead.
    const v = $(id).value.trim();
    return v;
  };
  let heightCm;
  if ($("height-unit").value === "ft-in") {
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
  if ($("target-unit").value === "st-lb") {
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
        tip_time: time("tip-time"),
        reminder_time: time("reminder-time"),
        reminder_weekday: Number($("reminder-weekday").value),
        exercise_time: time("exercise-time"),
        start_weight_override: num("start-override"),
      }),
    });
    // Email lives on the account, not the settings row: update it separately.
    const email = $("account-email").value.trim();
    if (email) {
      await fetchJson("/api/auth/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
    }
    toast("Settings saved");
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
  if ($("weight-unit").value === "st-lb") {
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
      body: JSON.stringify({ date, weight_kg: weightKg }),
    });
    $("entry-weight").value = "";
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

function syncWeightUnitUi() {
  const stLb = $("weight-unit").value === "st-lb";
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
  const ftIn = $("height-unit").value === "ft-in";
  $("height-cm").hidden = ftIn;
  $("height-ft-in").hidden = !ftIn;
  // Toggle required so the hidden cm field never blocks submit (same
  // hidden-required pitfall as the weight unit).
  $("height-cm").required = !ftIn;
  $("height-ft").required = ftIn;
  $("height-in").required = ftIn;
}

function syncTargetUnitUi() {
  const stLb = $("target-unit").value === "st-lb";
  $("target-weight").hidden = stLb;
  $("target-st-lb").hidden = !stLb;
  $("target-weight").required = !stLb;
  $("target-stone").required = stLb;
  $("target-lb").required = stLb;
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
  $("entry-form").addEventListener("submit", addEntry);
  $("settings-form").addEventListener("submit", saveSettings);
  $("enable-push").addEventListener("click", enablePush);
  $("disable-push").addEventListener("click", disablePush);
  $("test-push").addEventListener("click", testPush);
  $("entry-date").value = todayLocal();
  $("weight-unit").addEventListener("change", syncWeightUnitUi);
  $("height-unit").addEventListener("change", syncHeightUnitUi);
  $("target-unit").addEventListener("change", syncTargetUnitUi);
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
  try {
    await fetchJson("/api/auth/me");
    authenticated = true;
  } catch (_) {
    /* 401 (or a network error) leaves the gate visible. No scary toast on a
       fresh visit — the auth form surfaces errors when the user submits. */
  }
  if (authenticated) {
    showTracker();
    try {
      await loadData();
    } catch (err) {
      toast(`Could not load data: ${err.message}`);
    }
    await restorePushUi();
  } else if (resetToken) {
    showResetForm();
  }
}

init();
