"""SPA auth-gate delivery tests.

The gate is client-side (static files), so these assert the DELIVERED
artifacts: the served index.html ships the auth screen first with the tracker
hidden until authenticated, the auth helper script is served, and the fetch
wrapper keeps the same-origin credential posture (no `credentials: include`)
that makes the HttpOnly cookie flow work without leaking it cross-origin.

The behavioral rules of the gate (me() gates loadData, 401 returns to the
gate) are exercised end-to-end by the browser smoke script tests/smoke-ui.sh;
the auth API behind them is covered by test_auth_api.py.
"""

import ast
import json
import re

import pytest

from constants import EXERCISE_TYPES, HABIT_TYPES, QUEST_POOL


@pytest.mark.asyncio
async def test_index_html_ships_auth_gate_and_hidden_tracker(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    # The gate screen is present and the tracker starts hidden.
    assert 'id="auth-screen"' in html
    assert 'id="auth-form"' in html
    assert 'id="auth-username"' in html
    assert 'id="auth-password"' in html
    assert 'id="auth-toggle"' in html
    assert 'id="logout-btn"' in html
    assert 'id="tracker" hidden' in html


@pytest.mark.asyncio
async def test_index_html_loads_auth_helpers_before_app(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    # auth.js must load before app.js (app.js reads globalThis.AuthForm at
    # module scope), and format.js keeps its existing load order. The srcs
    # carry a ?v= cache-busting stamp.
    auth_at = html.find('src="/static/auth.js')
    app_at = html.find('src="/static/app.js')
    assert auth_at != -1 and app_at != -1 and auth_at < app_at
    assert 'src="/static/format.js' in html
    assert '?v=' in html  # cache busting is active
    # The stylesheet must carry the same version stamp: without it browsers
    # keep the old CSS indefinitely (ETag/Last-Modified only, no
    # Cache-Control) and CSS-only fixes appear broken after deploy.
    assert 'href="/static/style.css?v=' in html


@pytest.mark.asyncio
async def test_auth_js_is_served_with_validation_helpers(client):
    resp = await client.get("/static/auth.js")
    assert resp.status_code == 200
    body = resp.text
    assert "validateUsername" in body
    assert "validatePassword" in body
    assert "normalizeUsername" in body


@pytest.mark.asyncio
async def test_app_js_keeps_same_origin_fetch_posture(client):
    """The cookie flow depends on same-origin fetch; forcing
    credentials: 'include' would weaken the SameSite=Lax posture."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "credentials" not in body


@pytest.mark.asyncio
async def test_app_js_exercise_types_literal_matches_server_constant(client):
    """The SPA embeds the EXERCISE_TYPES literal that drives the exercise-type
    <select>; it must stay in sync with constants.EXERCISE_TYPES, which drives
    server-side validation. No /api/exercise-types endpoint exists by design."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    match = re.search(r"EXERCISE_TYPES\s*=\s*(\[[^\]]*\])", resp.text)
    assert match is not None, "app.js must embed the EXERCISE_TYPES literal"
    assert ast.literal_eval(match.group(1)) == list(EXERCISE_TYPES)


@pytest.mark.asyncio
async def test_habit_types_literal_matches_server_constant(client):
    """The SPA embeds the HABIT_TYPES literal that will drive the habit
    check-in UI; it must stay in sync with constants.HABIT_TYPES, which drives
    server-side validation. The quest-detection mapping (S3b) derives from the
    same server constant, so the four-value set stays pinned end-to-end. No
    /api/habit-types endpoint exists by design."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    match = re.search(r"HABIT_TYPES\s*=\s*(\[[^\]]*\])", resp.text)
    assert match is not None, "app.js must embed the HABIT_TYPES literal"
    assert ast.literal_eval(match.group(1)) == list(HABIT_TYPES)


@pytest.mark.asyncio
async def test_index_html_ships_onboarding_wizard_between_auth_and_tracker(client):
    """The onboarding wizard ships in the delivered HTML, starts hidden, sits
    between the auth gate and the tracker, and carries all six step blocks
    (goals-lifestyle between target and units) plus the target mode toggle,
    the optional goals/lifestyle fields, and the schedule fields the wizard
    submits."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    auth_at = html.find('id="auth-screen"')
    wizard_at = html.find('id="onboarding-screen"')
    tracker_at = html.find('id="tracker"')
    assert wizard_at != -1, "index.html must ship the onboarding screen"
    assert auth_at != -1 and tracker_at != -1 and auth_at < wizard_at < tracker_at
    assert 'id="onboarding-screen" hidden' in html
    # All six wizard steps ship, in order: height -> weight -> target ->
    # goals-lifestyle -> units -> notifications.
    for step_id in (
        "wizard-step-height",
        "wizard-step-weight",
        "wizard-step-target",
        "wizard-step-goals-lifestyle",
        "wizard-step-units",
        "wizard-step-notifications",
    ):
        assert f'id="{step_id}"' in html
    assert (
        html.find('id="wizard-step-height"')
        < html.find('id="wizard-step-weight"')
        < html.find('id="wizard-step-target"')
        < html.find('id="wizard-step-goals-lifestyle"')
        < html.find('id="wizard-step-units"')
        < html.find('id="wizard-step-notifications"')
    )
    # Goals & lifestyle step: the four optional fields (allowlists mirrored
    # from constants.PRIMARY_GOALS/ACTIVITY_LEVELS) live in the
    # #goals-lifestyle-form container; none of them are required.
    assert 'id="goals-lifestyle-form"' in html
    assert 'id="ob-primary-goal"' in html
    assert 'name="ob-secondary-goals"' in html
    assert 'name="ob-health-domains"' in html
    assert 'id="ob-activity-level"' in html
    # Target step: weight/BMI mode toggle + healthy-range hint container.
    assert 'name="ob-target-mode"' in html
    assert 'value="bmi"' in html
    assert 'id="ob-range-hint"' in html
    # Units step: weight_display + target_unit preferences.
    assert 'name="ob-weight-display"' in html
    assert 'name="ob-target-unit"' in html
    # Notifications step: schedule preferences (mandatory step, no skip button).
    assert 'id="ob-tip-time"' in html
    assert 'id="ob-reminder-time"' in html
    assert 'id="ob-reminder-weekday"' in html
    assert 'id="ob-exercise-time"' in html


@pytest.mark.asyncio
async def test_app_js_branches_on_needs_onboarding(client):
    """The wizard gate is client-side: app.js must read needs_onboarding off
    the /api/auth/me payload and show the wizard for flagged users without
    loading tracker data. Regex drift-guard in the style of the EXERCISE_TYPES
    literal test — behavior is exercised by tests/smoke-ui.sh."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "needs_onboarding" in body
    assert re.search(r"me\??\.needs_onboarding", body) is not None, (
        "app.js must branch on me().needs_onboarding"
    )
    assert "showOnboarding" in body, "app.js must define showOnboarding()"
    assert "showTracker" in body
    # The wizard submission posts the atomic OnboardingIn payload to the
    # Phase-3 endpoint; submitOnboarding must be wired up.
    assert '"/api/onboarding"' in body
    assert "submitOnboarding" in body
    # OnboardingIn keys the payload builder must produce.
    for key in (
        "height_cm",
        "weight_kg",
        "target_bmi",
        "target_weight",
        "weight_display",
        "reminder_weekday",
    ):
        assert key in body


# Design-token / font / favicon / asset-stamp gate additions for the
# game-appearance change. These assert the DELIVERED artifacts, so they parse
# the served CSS/HTML/manifest exactly as a browser would receive them.

# Token names the :root block must declare (design §Token Architecture).
_TOKEN_NAMES = (
    "--fox",
    "--gold",
    "--radius-sm",
    "--radius-md",
    "--radius-lg",
    "--radius-pill",
    "--shadow-1",
    "--shadow-2",
    "--shadow-3",
    "--space-1",
    "--space-2",
    "--space-3",
    "--space-4",
    "--space-5",
    "--font-display",
    "--font-body",
)

# main.py serves these with a ?v= cache stamp (the tuples are unchanged by
# this change; the gate verifies they still stamp correctly).
_STAMPED_ASSETS = (
    ("/static/style.css", "href"),
    ("/static/format.js", "src"),
    ("/static/auth.js", "src"),
    ("/static/app.js", "src"),
)


def _root_block(css: str) -> str:
    match = re.search(r":root\s*\{([^}]*)\}", css)
    assert match is not None, "style.css must declare a :root block"
    return match.group(1)


@pytest.mark.asyncio
async def test_style_css_ships_design_tokens_and_font_faces(client):
    """The served stylesheet must declare the game-appearance design tokens in
    :root and self-host Baloo 2 via versioned @font-face rules with a
    system-ui fallback in the font stacks (design §Token Architecture,
    spec 'Versioned font face')."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    root = _root_block(css)
    # Every token name is declared in :root.
    for token in _TOKEN_NAMES:
        assert re.search(rf"{token}\s*:", root) is not None, (
            f":root must declare {token}"
        )
    # Pinned token values (design §Token Architecture).
    assert re.search(r"--fox\s*:\s*#eb892c", root) is not None
    assert re.search(r"--gold\s*:\s*#f5c518", root) is not None
    assert re.search(r"--radius-sm\s*:\s*8px", root) is not None
    assert re.search(r"--radius-md\s*:\s*12px", root) is not None
    assert re.search(r"--radius-lg\s*:\s*18px", root) is not None
    assert re.search(r"--radius-pill\s*:\s*999px", root) is not None
    # Font stacks must lead with Baloo 2 and fall back to system-ui.
    assert re.search(r"--font-display\s*:\s*'Baloo 2'[^;]*system-ui", root) is not None
    assert re.search(r"--font-body\s*:\s*'Baloo 2'[^;]*system-ui", root) is not None
    # Self-hosted, filename-versioned woff2 @font-face rules (swap display).
    assert "baloo2-400.v1.woff2" in css
    assert "baloo2-600.v1.woff2" in css
    assert re.search(r"font-display\s*:\s*swap", css) is not None


@pytest.mark.asyncio
async def test_index_html_ships_fox_favicon_without_diamond(client):
    """The inline SVG favicon must be the fox glyph (fox-orange accents) and
    the diamond path must be gone (spec 'Fox favicon')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'rel="icon"' in html
    assert "%23eb892c" in html, "favicon must carry the fox-orange accent"
    assert "M32 8l14 22" not in html, "diamond favicon path must be removed"


@pytest.mark.asyncio
async def test_asset_tuples_carry_cache_stamps(client):
    """Every CSS/JS asset in the main.py tuples must be served with the ?v=
    cache stamp (spec 'Assets stamped')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    for asset, attr in _STAMPED_ASSETS:
        assert re.search(re.escape(asset) + r"\?v=", html) is not None, (
            f"{asset} must carry a ?v= stamp on its {attr} attribute"
        )


@pytest.mark.asyncio
async def test_manifest_theme_color_stays_brand_accent(client):
    """manifest.webmanifest theme_color must remain #2f7d54 (spec 'Fox
    favicon and manifest theme')."""
    resp = await client.get("/static/manifest.webmanifest")
    assert resp.status_code == 200
    manifest = json.loads(resp.text)
    assert manifest["theme_color"] == "#2f7d54"


# Phase 2 gate additions (game-appearance PR 2): the reduced-motion block,
# the mascot + wizard indicator markup, and the app.js component hooks that
# drive them (streak flame + data attr, wizard indicator sync, toast
# class-swap, token-driven chart palette).


# Phase 3 gate additions (game-appearance PR 3): the confetti wiring in app.js
# (fireConfetti + earned-count diff via shouldCelebrate + the reduced-motion
# matchMedia gate) and the motion CSS (flame pulse gated by the active-streak
# data attribute; confetti pieces; both neutralized in the reduced-motion
# block).


@pytest.mark.asyncio
async def test_style_css_ships_confetti_and_flame_motion(client):
    """The served stylesheet must ship the streak-flame pulse gated by the
    active-streak data attribute and the confetti-piece fall animation, and
    must neutralize both inside the prefers-reduced-motion block (spec
    'Motion system' + 'Reduced motion')."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    # Flame pulse: keyframes exist and are gated to the active-streak tile.
    assert "@keyframes flame-pulse" in css
    assert re.search(r'\[data-streak-active="true"\]\s+\.flame', css) is not None, (
        "flame pulse must be gated by the active-streak data attribute"
    )
    # Confetti pieces: fall keyframes + a rule binding the inline --color var.
    assert "@keyframes confetti-fall" in css
    assert ".confetti-piece" in css
    assert re.search(r"background\s*:\s*var\(--color\)", css) is not None, (
        "confetti pieces must fill from the inline token var"
    )
    # Both neutralized inside the reduced-motion block.
    media_at = css.index("@media (prefers-reduced-motion: reduce)")
    block = css[media_at:]
    assert re.search(
        r"\.confetti-piece\s*\{[^}]*display\s*:\s*none", block
    ) is not None, "reduced-motion must hide confetti pieces"
    assert re.search(
        r"flame[^}]*animation\s*:\s*none", block
    ) is not None, "reduced-motion must kill the flame pulse"


@pytest.mark.asyncio
async def test_style_css_ships_reduced_motion_block_without_starting_style(client):
    """The served stylesheet must ship a prefers-reduced-motion block that
    actually neutralizes motion, and must never use @starting-style (spec
    'Reduced motion': toast/tab reveals are JS class-swaps, not CSS start
    states)."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    assert "@media (prefers-reduced-motion: reduce)" in css, (
        "style.css must declare a prefers-reduced-motion: reduce block"
    )
    assert "@starting-style" not in css, (
        "style.css must not use @starting-style (reveals are JS class-swaps)"
    )
    # The block must actually neutralize animation/transition, not be a stub.
    media_at = css.index("@media (prefers-reduced-motion: reduce)")
    block = css[media_at:]
    assert block.rstrip().endswith("}"), "reduced-motion block must close"
    assert re.search(
        r"animation-duration|transition-duration|animation\s*:\s*none", block
    ) is not None, "reduced-motion block must neutralize animations/transitions"


@pytest.mark.asyncio
async def test_index_html_ships_mascot_and_wizard_indicator(client):
    """The header must carry the fox mascot (aria-hidden, before the h1) and
    the onboarding screen a 6-dot wizard indicator with no visible text
    (design D3, spec 'Motivation surfaces and mascot')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    header_row = html[html.index('<div class="header-row">') : html.index("</header>")]
    assert '<span class="mascot" aria-hidden="true">' in header_row
    assert header_row.index("mascot") < header_row.index("<h1>"), (
        "mascot must sit before the h1 in the header lockup"
    )
    onboarding = html[
        html.index('id="onboarding-screen"') : html.index('id="onboarding-form"')
    ]
    assert '<ol class="wizard-indicator">' in onboarding
    dots = re.findall(r'<li data-step="([^"]+)"></li>', onboarding)
    assert dots == [
        "height",
        "weight",
        "target",
        "goals-lifestyle",
        "units",
        "notifications",
    ], (
        "wizard indicator must carry the six step dots, in order, text-free"
    )


@pytest.mark.asyncio
async def test_app_js_ships_component_hooks(client):
    """app.js must wire the streak flame + active-streak data attribute, the
    wizard indicator .is-current sync with aria-current, and the toast
    .is-visible class-swap while keeping the [hidden] toggle (design
    'Component styling plan'; spec 'Motivation surfaces')."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    # Streaks: flame element + active-streak data attribute.
    assert "flame" in body
    assert "dataset.streakActive" in body
    # Wizard indicator sync in showWizardStep.
    assert 'classList.toggle("is-current"' in body
    assert 'setAttribute("aria-current"' in body
    # Toast: .is-visible class-swap while the [hidden] toggle stays.
    assert 'classList.add("is-visible")' in body
    assert "toastEl.hidden = false" in body
    assert "toastEl.hidden = true" in body


@pytest.mark.asyncio
async def test_app_js_drives_chart_colors_from_tokens(client):
    """app.js must read the chart palette ONCE from the design tokens via
    getComputedStyle (line --accent, grid --border, muted --muted, tooltip
    --text, tooltip text --card) and must not hardcode chart hex (design
    'Canvas colors/font')."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "CHART_COLORS" in body
    assert "CHART_FONT" in body
    assert "getComputedStyle" in body
    for hardcoded in ("#94a3b8", "#e2e8f0", "#f8fafc", "rgba(15, 23, 42"):
        assert hardcoded not in body, (
            f"chart code must not hardcode {hardcoded}"
        )


# Phase 3 gate additions (game-appearance PR 3): the confetti wiring in app.js
# (fireConfetti + earned-count diff via shouldCelebrate + the reduced-motion
# matchMedia gate) and the motion CSS (flame pulse gated by the active-streak
# data attribute; confetti pieces; both neutralized in the reduced-motion
# block).


@pytest.mark.asyncio
async def test_app_js_ships_confetti_wiring(client):
    """app.js must wire confetti to the earned-count diff: fireConfetti()
    defined, shouldCelebrate() consulted inside loadData, module prevEarned
    state, and the prefers-reduced-motion matchMedia gate (design §Confetti,
    spec 'Confetti eligibility' + 'Reduced motion')."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "function fireConfetti" in body
    assert "shouldCelebrate(" in body
    assert "let prevEarned = null" in body
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in body


# ---- dark-mode S1: [data-theme="dark"] block + toast tokens ----------------
# The dark block MUST use the bare-stripped `[data-theme="dark"]` selector
# (design D1) so the gate `_root_block` regex `:root\s*\{` can never collide
# with it; the pinned token values come from design §CSS. `--accent` must NOT
# be redeclared in the dark block (palette lockstep stays #2f7d54 in :root).

_DARK_TOKENS = {
    "--bg": "#0f172a",
    "--card": "#1e293b",
    "--text": "#e2e8f0",
    "--muted": "#94a3b8",
    "--border": "#334155",
    "--accent-dark": "#58a97e",
    "--danger": "#f06a5d",
    "--fox": "#f5a850",
    "--gold": "#fbd34a",
    "--gold-deep": "#e0b020",
    "--toast-bg": "#1e293b",
    "--toast-text": "#e2e8f0",
}


@pytest.mark.asyncio
async def test_style_css_ships_dark_theme_block_with_pinned_tokens(client):
    """The served stylesheet must declare a [data-theme="dark"] block after
    :root redefining the semantic tokens to the pinned dark values, and must
    NOT redeclare --accent (design §CSS, spec 'Dark token block')."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    match = re.search(r'\[data-theme="dark"\]\s*\{([^}]*)\}', css)
    assert match is not None, (
        'style.css must declare a [data-theme="dark"] block'
    )
    block = match.group(1)
    for token, value in _DARK_TOKENS.items():
        assert re.search(rf"{token}\s*:\s*{re.escape(value)}", block) is not None, (
            f"dark block must declare {token}: {value}"
        )
    # --accent stays the brand anchor in :root; never redeclared in dark.
    assert re.search(r"--accent\s*:", block) is None, (
        "--accent must not be redeclared in the dark block"
    )


@pytest.mark.asyncio
async def test_style_css_has_exactly_one_bare_root_selector(client):
    """The dark block MUST use [data-theme="dark"], never a bare `:root {`
    (gate `_root_block` regex collision guard, design D1): the stylesheet may
    contain exactly one `:root\\s*\\{` selector — the real :root block."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    assert len(re.findall(r":root\s*\{", css)) == 1, (
        "exactly one bare :root { selector allowed; dark block must use "
        '[data-theme="dark"]'
    )


@pytest.mark.asyncio
async def test_index_html_has_no_media_variant_theme_color_meta(client):
    """No `<meta name="theme-color" media=...>` variant may exist — palette
    lockstep requires name immediately followed by content (spec 'Accent
    constant across themes')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    for meta in re.findall(r"<meta[^>]*>", html):
        if 'name="theme-color"' in meta:
            assert "media=" not in meta, (
                "theme-color meta must not carry a media variant"
            )


@pytest.mark.asyncio
async def test_style_css_toast_tokens_declared_in_root_and_consumed(client):
    """Toast colors must be tokenized: --toast-bg/--toast-text declared in
    :root and consumed by .toast, with no hardcoded rgba background left in
    the rule (spec 'Toast tokenized')."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    root = _root_block(css)
    assert re.search(r"--toast-bg\s*:", root) is not None, (
        ":root must declare --toast-bg"
    )
    assert re.search(r"--toast-text\s*:", root) is not None, (
        ":root must declare --toast-text"
    )
    toast = re.search(r"\.toast\s*\{([^}]*)\}", css)
    assert toast is not None, "style.css must declare a .toast rule"
    toast_body = toast.group(1)
    assert "var(--toast-bg)" in toast_body, ".toast must consume --toast-bg"
    assert "var(--toast-text)" in toast_body, ".toast must consume --toast-text"
    assert "rgba(15,23,42" not in toast_body, (
        ".toast must not hardcode the rgba background"
    )


# ---- dark-mode S2: JS theming lifecycle + UX surfaces ----------------------
# Phase 4 gate additions (dark-mode PR 2): app.js must ship the JS theme
# lifecycle hooks (applyTheme / refreshChartColors / resolveTheme / the
# prefers-color-scheme matchMedia listener) and index.html the UX surfaces
# (FOUC-safe head script, #theme-toggle, Appearance radio group).


@pytest.mark.asyncio
async def test_app_js_ships_theme_lifecycle_hooks(client):
    """app.js must define applyTheme + refreshChartColors, consume
    resolveTheme from format.js, and register a prefers-color-scheme
    matchMedia listener (design D5: system-follow without reload)."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "function applyTheme" in body, "app.js must define applyTheme()"
    assert "function refreshChartColors" in body, (
        "app.js must define refreshChartColors()"
    )
    assert "resolveTheme(" in body, "app.js must consume resolveTheme"
    assert 'matchMedia("(prefers-color-scheme: dark)")' in body, (
        "app.js must read the system color scheme via matchMedia"
    )
    assert "addEventListener" in body and "removeEventListener" in body, (
        "app.js must add/remove the matchMedia change listener"
    )
    # The system-follow listener must be gated to "system" mode (D5): the
    # add/remove branch keys off the theme preference value.
    assert re.search(r'=== "system"', body) is not None, (
        "app.js must branch on the \"system\" pref for the listener"
    )


@pytest.mark.asyncio
async def test_index_html_ships_fouc_head_script(client):
    """index.html must carry a FOUC-safe inline <head> script that sets
    data-theme pre-paint: localStorage first, matchMedia fallback, no
    media-variant meta (design §JS Theming Lifecycle, spec 'FOUC-Safe
    Pre-Auth Theming')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    head = html[html.index("<head>") : html.index("</head>")]
    assert "localStorage.getItem(\"theme\")" in head, (
        "FOUC script must read the persisted theme from localStorage"
    )
    assert 'matchMedia("(prefers-color-scheme: dark)")' in head, (
        "FOUC script must fall back to the system color scheme"
    )
    assert "documentElement.dataset.theme" in head, (
        "FOUC script must set data-theme on <html> before paint"
    )
    assert "<script>" in head, "FOUC bootstrap must be a <script>, not a meta"


@pytest.mark.asyncio
async def test_index_html_ships_theme_toggle_beside_logout(client):
    """The header must ship #theme-toggle (always visible, beside
    #logout-btn) with an aria-label (design D3: visible pre-auth; D4:
    grouped with logout at flex-end)."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    header_row = html[html.index('<div class="header-row">') : html.index("</header>")]
    assert 'id="theme-toggle"' in header_row
    assert "aria-label=" in header_row, "theme toggle must carry an aria-label"
    toggle_at = header_row.index('id="theme-toggle"')
    logout_at = header_row.index('id="logout-btn"')
    assert toggle_at < logout_at, "theme-toggle must sit before #logout-btn"
    # D3: the toggle is always visible — no hidden attribute (unlike logout).
    assert "hidden" not in header_row[header_row.index('id="theme-toggle"') : logout_at], (
        "theme toggle must be visible pre-auth (no hidden attribute)"
    )


@pytest.mark.asyncio
async def test_index_html_ships_appearance_radio_group(client):
    """The Me tab must ship the three-state Appearance radio group
    (name="appearance": system/light/dark) that drives the same theme
    setting as the header toggle (spec 'Theme UX Surfaces')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    # Slice the whole Me panel: from the tab-panel open tag up to the last
    # card in it (push-card), so every Me card is included.
    settings = html[html.index('id="tab-me"') : html.index('id="push-card"')]
    assert 'name="appearance"' in settings
    for value in ("system", "light", "dark"):
        assert f'name="appearance" value="{value}"' in settings, (
            f"Appearance radio group must ship value {value!r}"
        )
    # The radio group must live in a card after the Units & display card
    # (design §JS Theming Lifecycle: Appearance card after weight-display).
    assert 'id="tab-me"' in html
    assert "Appearance" in settings, "the Appearance card must ship in Me"
    assert 'name="weight-display"' in settings, "weight-display group must still ship"
    assert settings.index('name="weight-display"') < settings.index('name="appearance"'), (
        "Appearance card must come after the Units & display card"
    )


# ---- R0 navigation restructure gate additions (feat/r0-nav) ---------------
# The tabbed SPA was restructured from (today/progress/history/settings) to
# (today/journey/world/me): Journey absorbs the old Progress charts and the
# History entry lists (the longitudinal view, strategy §6.2), World is the XP
# island, and Me absorbs the old Settings panel. These assert
# the DELIVERED structure so the smoke's tab flow keeps working (spec 'R0
# Navigation Restructure').


@pytest.mark.asyncio
async def test_index_html_ships_four_tab_buttons(client):
    """The tab bar must ship exactly the four buttons today/journey/world/me,
    in order, with Today active and the rest inactive."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    nav = html[html.index('<nav class="tabs"') : html.index("</nav>")]
    buttons = re.findall(r'data-tab="([^"]+)"', nav)
    assert buttons == ["today", "journey", "world", "me"], (
        "tab bar must ship today/journey/world/me in order"
    )
    assert 'data-tab="today" role="tab" aria-selected="true"' in nav
    for tab in ("journey", "world", "me"):
        assert f'data-tab="{tab}" role="tab" aria-selected="false"' in nav


@pytest.mark.asyncio
async def test_index_html_journey_panel_absorbs_charts_and_history(client):
    """The Journey panel must ship the old Progress chart canvases AND the old
    History entry lists — journey is the longitudinal view (strategy §6.2)."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert (
        html.index('id="tab-today"')
        < html.index('id="tab-journey"')
        < html.index('id="tab-world"')
        < html.index('id="tab-me"')
    ), "panels must order today < journey < world < me"
    journey = html[html.index('id="tab-journey"') : html.index('id="tab-world"')]
    for needle in (
        '<canvas id="chart" height',
        '<canvas id="chart-exercise" height',
        '<canvas id="chart-meals" height',
        '<ul class="entry-list" id="entry-list">',
        'id="exercise-list"',
        'id="meal-list"',
    ):
        assert needle in journey, f"Journey panel must ship {needle}"


# ---- r2-world-xp-island S2 gate additions: static XP island --------------
# One accessible SVG, five ordered data-stage groups, fox at the terminal
# stage, token fills (never raw hex) (spec 'Island Evolution and Appearance').
_ISLAND_TOKENS = (
    "--island-sky", "--island-sea", "--island-ground", "--island-foliage",
    "--island-foliage-deep", "--island-trunk", "--island-flower",
    "--island-sun", "--island-fox-face", "--island-fox-eye",
)
_STAGE_NAMES = ("sprout", "sapling", "tree", "lush", "thriving")


@pytest.mark.asyncio
async def test_index_html_world_panel_ships_xp_island(client):
    """World panel ships #world-card with one accessible #world-island SVG at
    stage 1, five ordered data-stage groups, fox only in stage 5, token-only
    fills, no placeholder; CSS declares island tokens in :root + dark, one
    stage per data-current-stage, and kills island motion on reduced-motion."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    world = html[html.index('id="tab-world"') : html.index('id="tab-me"')]

    # Card + island ship at the static stage-1 default (Slice 3 wires runtime).
    for needle in (
        'id="world-card"',
        'id="world-island"',
        'data-current-stage="1"',
        'id="world-stage-name"',
        'id="world-progress"',
    ):
        assert needle in world, f"World panel must ship {needle}"

    # One accessible inline SVG island.
    assert world.count("<svg") == 1, "World panel must ship exactly one SVG"
    svg = world[world.index("<svg") : world.index("</svg>") + len("</svg>")]
    assert 'role="img"' in svg and "aria-label=" in svg

    # Five stage groups in order; fox only inside the stage-5 group.
    stages = re.findall(
        r'<g[^>]*data-stage="([^"]+)" data-stage-name="([^"]+)">', world
    )
    assert [num for num, _ in stages] == ["1", "2", "3", "4", "5"]
    assert [name for _, name in stages] == list(_STAGE_NAMES)
    fox_in = {}
    for num in ("1", "2", "3", "4", "5"):
        start = world.index(f'data-stage="{num}"')
        end_marker = f'data-stage="{int(num) + 1}"' if int(num) < 5 else "</svg>"
        fox_in[num] = "island-fox" in world[start : world.index(end_marker, start)]
    assert fox_in == {"1": False, "2": False, "3": False, "4": False, "5": True}

    # Fills are token classes, never raw hex; no placeholder copy.
    assert re.search(r'fill\s*=\s*["\']#', svg) is None
    assert re.search(r'class="island-', svg) is not None
    assert "Your adventure map is coming soon." not in world

    # CSS: island tokens in :root + dark; foliage-deep lockstep with brand.
    css = (await client.get("/static/style.css")).text
    root = _root_block(css)
    dark = re.search(r'\[data-theme="dark"\]\s*\{([^}]*)\}', css)
    assert dark is not None, 'style.css must declare a [data-theme="dark"] block'
    for token in _ISLAND_TOKENS:
        assert re.search(rf"{token}\s*:", root) is not None
        assert re.search(rf"{token}\s*:", dark.group(1)) is not None
    assert re.search(r"--island-foliage-deep\s*:\s*#2f7d54", root) is not None

    # One stage visible per data-current-stage.
    assert re.search(
        r"#world-island\s+\[data-stage\]\s*\{[^}]*display\s*:\s*none", css
    )
    for num in ("1", "2", "3", "4", "5"):
        assert re.search(
            rf'#world-island\[data-current-stage="{num}"\]\s+\[data-stage="{num}"\]',
            css,
        )

    # Island SVG rules are token-only (no hex); reduced-motion kills motion.
    island_rules = list(re.finditer(r"\.island-[a-z-]+\s*\{[^}]*}", css))
    assert island_rules, "style.css must declare island SVG rules"
    for rule in island_rules:
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0)) is None
    media = css[css.index("@media (prefers-reduced-motion: reduce)"):]
    assert re.search(r"\.island-stage[^}]*animation\s*:\s*none", media)


@pytest.mark.asyncio
async def test_index_html_me_panel_ships_old_settings_forms(client):
    """The Me panel must absorb the old Settings panel: account, goal & body,
    units & display, appearance, reminders, and push cards all ship under
    #tab-me (spec 'R0 Navigation Restructure')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    me = html[html.index('id="tab-me"') : html.index("</main>")]
    for needle in (
        'id="account-form"',
        'id="goal-form"',
        'id="display-form"',
        'id="appearance-form"',
        'id="reminders-form"',
        'id="push-card"',
        'id="target-weight"',
        'id="height-cm"',
        'id="start-override"',
    ):
        assert needle in me, f"Me panel must ship {needle}"


@pytest.mark.asyncio
async def test_index_html_has_no_old_tab_remnants(client):
    """No progress/history/settings remnants may remain in index.html: neither
    tab buttons, panel ids, nor the footer's Settings reference (spec 'R0
    Navigation Restructure')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    for remnant in (
        'data-tab="progress"',
        'data-tab="history"',
        'data-tab="settings"',
        'id="tab-progress"',
        'id="tab-history"',
        'id="tab-settings"',
        ">Progress</button>",
        ">History</button>",
        ">Settings</button>",
    ):
        assert remnant not in html, f"index.html must not ship {remnant}"
    assert "chosen in Settings" not in html, (
        "footer must reference the Me tab, not the removed Settings tab"
    )


@pytest.mark.asyncio
async def test_app_js_redraws_charts_on_journey_tab(client):
    """switchTab stays generic (data-tab / .tab-panel / .tab-btn) but the canvas
    redraw that used to trigger for 'progress' must now trigger for 'journey'
    (the charts live there); applyTheme redraws only when the Journey panel is
    visible (spec 'R0 Navigation Restructure')."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    # switchTab stays generic...
    assert "btn.dataset.tab === name" in body, (
        "switchTab must stay keyed off data-tab"
    )
    assert "panel.id !== `tab-${name}`" in body, (
        "switchTab must keep the [hidden] panel toggle"
    )
    # ...and redraws the charts when the Journey tab is shown.
    assert 'if (name === "journey")' in body, (
        "switchTab must redraw charts on the Journey tab"
    )
    assert 'name === "progress"' not in body, (
        "switchTab must not branch on the removed progress tab"
    )
    # applyTheme redraws only when the Journey panel is visible.
    assert 'if (!$("tab-journey").hidden)' in body, (
        "applyTheme must redraw charts only when the Journey panel is visible"
    )
    assert '"tab-progress"' not in body, (
        "app.js must not reference the removed progress panel"
    )


# ---- goals-dashboard S1 gate additions (PR 1): mirror helpers + ring container ----
# The helper test asserts the DELIVERED format.js ships the three mirror helpers
# contiguously on the api export (spec 'Goal Progress and Threshold Mirror
# Helpers'); the container test pins the hero ring div inside #summary-card
# (spec 'Goal Progress Ring', design §File Changes S1 row).


@pytest.mark.asyncio
async def test_format_js_ships_goal_helpers(client):
    """The served format.js must ship the goals-dashboard mirror helpers
    goalProgress/checkpointThresholds/kgToImperial, registered together on the
    WeightFormat api export (spec 'Goal Progress and Threshold Mirror
    Helpers')."""
    resp = await client.get("/static/format.js")
    assert resp.status_code == 200
    body = resp.text
    for helper in ("goalProgress", "checkpointThresholds", "kgToImperial"):
        assert helper in body, f"format.js must ship {helper}"
    # All three must be registered on the api export, not just defined.
    assert "goalProgress, checkpointThresholds, kgToImperial" in body, (
        "the three helpers must be registered together on the api export"
    )


@pytest.mark.asyncio
async def test_index_html_ships_goal_ring_container(client):
    """The Today tab must ship the hero goal-ring container inside
    #summary-card, after its h2 and before #summary-stats (design §File
    Changes; spec 'Goal Progress Ring')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    summary = html[html.index('id="summary-card"') : html.index('id="summary-stats"')]
    assert 'class="goal-ring" id="goal-ring"' in summary, (
        "summary-card must ship the goal-ring container"
    )
    assert 'aria-hidden="true"' in summary, "goal-ring must be aria-hidden"
    assert summary.index("<h2>") < summary.index('id="goal-ring"'), (
        "goal-ring must sit after the summary h2"
    )


# ---- goals-dashboard S2 gate additions (PR 2): ring renderer + ring/streak CSS ----
# The renderer test asserts the DELIVERED app.js ships renderGoalRing wired into
# loadData (destructuring goalProgress from the format.js api S1 shipped); the
# empty-state copy test pins the null-goal helper copy; the CSS test pins the
# ring/streak styles incl. the reduced-motion neutralization (spec 'Goal
# Progress Ring', design §Ring SVG math / §Streak tile upgrade).


@pytest.mark.asyncio
async def test_app_js_ships_goal_ring_renderer(client):
    """app.js must destructure goalProgress from WeightFormat, define
    renderGoalRing building the ring SVG (stroke-dasharray/stroke-dashoffset,
    url(#goalGrad)), and call it in loadData after renderSummary (design §Ring
    SVG math; spec 'Goal Progress Ring')."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "function renderGoalRing" in body, (
        "app.js must define renderGoalRing()"
    )
    # goalProgress must be destructured from the format.js api (S1 helper).
    assert re.search(
        r"\{[^}]*goalProgress[^}]*\}\s*=\s*globalThis\.WeightFormat", body
    ) is not None, "app.js must destructure goalProgress from WeightFormat"
    # Ring SVG construction strings (design: stroke-dasharray=C, dashoffset=C*(1-pct)).
    assert "stroke-dasharray" in body
    assert "stroke-dashoffset" in body
    assert 'stroke="url(#goalGrad)"' in body, (
        "ring progress stroke must reference the #goalGrad gradient"
    )
    # Wired into loadData after renderSummary(weight.summary).
    assert "renderSummary(weight.summary);" in body
    assert "renderGoalRing(chartData.weightSummary);" in body, (
        "loadData must call renderGoalRing with chartData.weightSummary"
    )
    assert body.index("renderGoalRing(chartData.weightSummary);") > body.index(
        "renderSummary(weight.summary);"
    ), "renderGoalRing must run after renderSummary in loadData"


@pytest.mark.asyncio
async def test_app_js_ships_ring_empty_state_copy(client):
    """The null-goal empty state must ship helper copy (spec 'Goal Progress
    Ring' edge scenario). The copy is generated by renderGoalRing, so it is
    asserted on the served app.js (task name deviates from tasks.md's
    index_html label for that reason)."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "Set a target weight to start tracking." in body, (
        "app.js must ship the ring empty-state helper copy"
    )


@pytest.mark.asyncio
async def test_style_css_ships_goal_ring_and_streak_rules(client):
    """style.css must ship the ring styles: .goal-ring container, token-only
    track stroke (var(--border)), the #goalGrad gradient stops from tokens
    (no chart hex), the stroke-dashoffset transition neutralized inside the
    prefers-reduced-motion block, and the streak tile flame/value sizing
    (design §Ring SVG math, §Streak tile upgrade; spec 'Goal Progress Ring')."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    assert re.search(r"\.goal-ring\s*\{", css) is not None, (
        "style.css must declare a .goal-ring rule"
    )
    assert re.search(r"\.goal-ring-track\s*\{[^}]*var\(--border\)", css) is not None, (
        "ring track stroke must use var(--border)"
    )
    # Progress stroke transition (design: stroke-dashoffset .5s ease).
    assert re.search(r"transition\s*:\s*stroke-dashoffset", css) is not None, (
        "ring progress must carry a stroke-dashoffset transition"
    )
    # #goalGrad gradient stops consume tokens, never chart hex.
    assert re.search(r"#goalGrad[^}]*var\(--fox\)", css) is not None, (
        "#goalGrad must start from var(--fox)"
    )
    assert re.search(r"#goalGrad[^}]*var\(--accent\)", css) is not None, (
        "#goalGrad must end at var(--accent)"
    )
    # The stroke-dashoffset transition is neutralized inside the reduced-motion block.
    media_at = css.index("@media (prefers-reduced-motion: reduce)")
    block = css[media_at:]
    assert re.search(
        r"\.goal-ring-progress[^}]*transition\s*:\s*none", block
    ) is not None, (
        "reduced-motion block must neutralize the ring progress transition"
    )
    # Streak tile upgrade sizing (flame 1.7rem, value 1.3rem).
    assert re.search(r"\.streak-tile\s+\.flame\s*\{[^}]*1\.7rem", css) is not None, (
        "streak tile flame must size up to 1.7rem"
    )
    assert re.search(r"\.streak-tile\s+\.stat-value\s*\{[^}]*1\.3rem", css) is not None, (
        "streak tile value must size up to 1.3rem"
    )


# ---- milestone strip gate additions (UI refinement): achieved-dot strip + next line ----
# The strip test asserts the DELIVERED app.js ships the one-line achieved-milestone
# strip: milestone-strip/milestone-dot/is-last-achieved/milestone-next construction
# strings, the checkpointThresholds/kgToImperial/milestoneNextLabel destructure, the
# per-dot data-percent hook, and NO remnants of the old five-card grid (milestone-card
# / milestone-grid / is-pending gone). The next-line test pins the pure
# milestoneNextLabel builder on the format.js api export. The gold test pins the
# last-achieved dot ring: gold styles the border/box-shadow/background only, never a
# text color property (spec '100% gold is fill-only').


@pytest.mark.asyncio
async def test_app_js_ships_milestone_strip(client):
    """app.js must build the achieved-milestone strip: destructure
    checkpointThresholds + kgToImperial + milestoneNextLabel from WeightFormat,
    emit .milestone-strip with a .milestone-dot (data-percent) per ACHIEVED
    checkpoint, mark the max-percent dot .is-last-achieved, and render the
    text-only .milestone-next line; the old five-card grid classes must be
    gone (design §Milestone strip; spec 'Five-Card Milestone Track')."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    # Strip + dot + next-line construction strings.
    assert '"milestone-strip"' in body, (
        "app.js must build a .milestone-strip container"
    )
    assert '"milestone-dot"' in body, (
        "app.js must emit .milestone-dot elements"
    )
    assert '"is-last-achieved"' in body, (
        "app.js must mark the max-percent dot .is-last-achieved"
    )
    assert '"milestone-next"' in body, (
        "app.js must render the .milestone-next text line"
    )
    assert "data-percent" in body, (
        "each milestone dot must carry data-percent"
    )
    # The strip helpers must be destructured from the format.js api.
    for helper in ("checkpointThresholds", "kgToImperial", "milestoneNextLabel"):
        assert re.search(
            rf"\{{[^}}]*{helper}[^}}]*\}}\s*=\s*globalThis\.WeightFormat", body
        ) is not None, f"app.js must destructure {helper} from WeightFormat"
    # All-earned copy ships (next_checkpoint null with a goal set).
    assert "All checkpoints earned!" in body
    # The old five-card grid is gone from app.js (pending dots are not in the DOM).
    assert '"milestone-card"' not in body, (
        "the old .milestone-card grid must be removed from app.js"
    )
    assert '"milestone-grid"' not in body, (
        "the old .milestone-grid container must be removed from app.js"
    )
    assert "is-pending" not in body, (
        "pending-milestone classes must be gone (pending dots are not rendered)"
    )
    # Pinned per-percent emoji set (design: 🚶🏃🔥🏆🎯 for 10/25/50/75/100).
    for emoji in ("🚶", "🏃", "🔥", "🏆", "🎯"):
        assert emoji in body, f"app.js must map an emoji per milestone percent ({emoji})"


@pytest.mark.asyncio
async def test_format_js_ships_milestone_next_builder(client):
    """format.js must ship milestoneNextLabel — the pure builder for the
    strip's next-milestone text line ('Next: {percent}% at ...'), registered on
    the WeightFormat api export (spec 'Five-Card Milestone Track')."""
    resp = await client.get("/static/format.js")
    assert resp.status_code == 200
    body = resp.text
    assert "function milestoneNextLabel" in body, (
        "format.js must define milestoneNextLabel()"
    )
    assert re.search(r"kgToImperial,\s*milestoneNextLabel", body) is not None, (
        "milestoneNextLabel must be registered on the api export"
    )


# Journey progress cards (r1-quests-xp S4b): the XP, momentum, and quest
# history card markup inside the Journey panel, the app.js renderer hooks, the
# failure-scoped momentum load, and the token-only journey CSS with
# reduced-motion neutralization. Behavior (populated + empty renders) is
# exercised by tests/smoke-ui.sh; these gate the delivered artifacts.


@pytest.mark.asyncio
async def test_journey_progress_surfaces(client):
    """Journey must ship #xp-card, #momentum-card, and #quest-history-card
    inside the Journey panel; app.js must define the three renderers and load
    momentum failure-scoped; the new CSS must be token-only with reduced-motion
    neutralization (spec 'Journey Progress Cards' + 'Journey UI Regression
    Contract')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    journey = html[html.index('id="tab-journey"') : html.index('id="tab-world"')]
    for needle in ('id="xp-card"', 'id="momentum-card"', 'id="quest-history-card"'):
        assert needle in journey, f"Journey panel must ship {needle}"
    # The pre-existing absorb pin must remain: the panel keeps its chart
    # canvases and history lists (spec 'Journey UI Regression Contract').
    assert '<canvas id="chart" height' in journey
    assert '<ul class="entry-list" id="entry-list">' in journey

    app = await client.get("/static/app.js")
    assert app.status_code == 200
    body = app.text
    for hook in ("renderJourneyXp", "renderMomentum", "renderQuestHistory"):
        assert hook in body, f"app.js must define {hook}"
    # Journey loading must be failure-scoped: momentum via Promise.allSettled.
    assert "Promise.allSettled" in body
    assert re.search(r"fetchJson\(\"/api/momentum\"\)", body) is not None, (
        "app.js must fetch /api/momentum"
    )
    # Non-done history rows award zero XP: the renderer must branch on status.
    assert re.search(r"status\s*[!=]==\s*[\"']done[\"']", body) is not None, (
        "quest-history renderer must branch on done vs non-done XP"
    )

    css = await client.get("/static/style.css")
    assert css.status_code == 200
    sheet = css.text
    for selector in (".journey-xp", ".momentum-tier", ".quest-history"):
        assert selector in sheet, f"style.css must declare {selector}"
    # Token-only: the new surface rules must not introduce palette hex.
    # Materialize the matches first so a missing rule family fails the
    # non-empty assertion instead of silently running zero checks (ghost-loop
    # guard, strict TDD).
    journey_rules = list(re.finditer(
        r"\.(?:journey|momentum|quest-history)[a-z-]*\s*\{[^}]*}", sheet
    ))
    assert len(journey_rules) > 0, "style.css must declare journey/momentum/history rules"
    for rule in journey_rules:
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0)) is None, (
            "journey/momentum/history CSS must be token-only (no hex literals)"
        )
    # Reduced motion: the new surfaces' transitions are neutralized.
    media_at = sheet.index("@media (prefers-reduced-motion: reduce)")
    block = sheet[media_at:]
    for selector in (".xp-card", ".momentum-card", ".quest-history-card"):
        assert re.search(
            re.escape(selector) + r"[^}]*transition\s*:\s*none", block
        ), f"reduced-motion must neutralize {selector}"


# Today quests + XP chip (r1-quests-xp S4a): the quests card markup, the
# format.js XP mirrors, the app.js renderer/mutation hooks, and the
# token-only quest/chip CSS with reduced-motion neutralization. Behavior
# (complete/skip/replace flows, replace-cap 409, chip progress) is exercised
# by tests/smoke-ui.sh; these gate the delivered artifacts.


@pytest.mark.asyncio
async def test_today_quest_surface(client):
    """The Today tab must ship #quests-card (with an open-row action surface
    and an accessible error region) and #xp-summary-chip (with a content
    container) inside #tab-today; format.js must expose the XP curve mirrors;
    app.js must wire the quest renderer, the mutation flow (disable-while-
    pending, error feedback that never removes the card), and the XP chip
    renderer, loading both via Promise.allSettled so one failed fetch never
    blanks the Today view; style.css must style the surfaces token-only and
    neutralize their transitions under prefers-reduced-motion."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    today = html[html.index('id="tab-today"') : html.index('id="tab-journey"')]
    # Quests card: container + row list + accessible error region, all inside
    # the Today panel.
    assert 'id="quests-card"' in today
    assert 'id="quests-list"' in today
    assert 'id="quests-error"' in today
    assert 'role="alert"' in today
    # XP summary chip: card + content container, inside the Today panel.
    assert 'id="xp-summary-chip"' in today
    assert 'id="xp-chip-content"' in today

    fmt = await client.get("/static/format.js")
    assert fmt.status_code == 200
    for mirror in ("thresholdForLevel", "levelFromXp", "xpIntoNext"):
        assert mirror in fmt.text, f"format.js must expose {mirror}"

    app = await client.get("/static/app.js")
    assert app.status_code == 200
    body = app.text
    for hook in ("renderQuests", "mutateQuest", "renderXpChip"):
        assert hook in body, f"app.js must define {hook}"
    # R1 loading must be failure-scoped: quests + XP via Promise.allSettled.
    assert "Promise.allSettled" in body
    assert re.search(r"fetchJson\(\"/api/quests\"\)", body) is not None
    assert re.search(r"fetchJson\(\"/api/xp\"\)", body) is not None
    # The quest action surface: delegated open-row controls driven by
    # data-action attributes (complete/skip/replace).
    assert '"complete"' in body
    assert '"skip"' in body
    assert '"replace"' in body
    assert 'classList.add("quest-action")' in body or 'className = "quest-action"' in body
    assert re.search(r'"quests-list".*addEventListener', body) is not None

    css = await client.get("/static/style.css")
    assert css.status_code == 200
    sheet = css.text
    for selector in (".quest-row", ".quest-action", ".xp-chip"):
        assert selector in sheet, f"style.css must declare {selector}"
    # Token-only: the new surface rules must not introduce palette hex.
    # Materialize the matches first so a missing rule family fails the
    # non-empty assertion instead of silently running zero checks (ghost-loop
    # guard, strict TDD).
    today_rules = list(re.finditer(r"\.quest-[a-z-]+\s*\{[^}]*}|\.[a-z-]*xp-chip[a-z-]*\s*\{[^}]*}", sheet))
    assert len(today_rules) > 0, "style.css must declare quest/chip rules"
    for rule in today_rules:
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0)) is None, (
            "quest/chip CSS must be token-only (no hex literals)"
        )
    # Reduced motion: the new surfaces' transitions are neutralized.
    media_at = sheet.index("@media (prefers-reduced-motion: reduce)")
    block = sheet[media_at:]
    assert re.search(r"\.quest-row[^}]*transition\s*:\s*none", block) is not None, (
        "reduced-motion must neutralize quest row transitions"
    )
    assert re.search(r"\.quest-action[^}]*transition\s*:\s*none", block) is not None, (
        "reduced-motion must neutralize quest action transitions"
    )


@pytest.mark.asyncio
async def test_style_css_gold_is_fill_only(client):
    """Gold must style the last-achieved dot as a ring/fill only: border-color
    and box-shadow from var(--gold)/color-mix, never any text color property
    anywhere in the sheet (spec '100% gold is fill-only')."""
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    css = resp.text
    rule = re.search(r"\.milestone-dot\.is-last-achieved\s*\{([^}]*)\}", css)
    assert rule is not None, (
        "style.css must declare a .milestone-dot.is-last-achieved rule"
    )
    body = rule.group(1)
    # Gold rings the dot (border/box-shadow/background) — fill-only by design.
    assert "var(--gold" in body, "the last-achieved dot must carry a gold ring"
    stripped = re.sub(r"(?:background|border-color|box-shadow)[^;]*;", "", body)
    assert "var(--gold" not in stripped, (
        "the last-achieved dot must not apply gold to its text color"
    )
    # Gold must never be a text color anywhere in the sheet (fill-only).
    assert re.search(r"(?<!-)color\s*:\s*var\(--gold", css) is None, (
        "gold must never be applied to a text color property"
    )


# Journey achievements card (r2-achievements S3): the #achievements-card markup
# immediately after #momentum-card, the app.js read-diff/confetti wiring
# (renderAchievements + newAchievementKeys destructure + prevAchievementKeys
# state + card-scoped failure), the format.js newAchievementKeys export, and
# the token-only achievement CSS with reduced-motion neutralization. Behavior
# (six earned/locked rows, no partial progress, card order) is exercised by
# tests/smoke-ui.sh; these gate the delivered artifacts (spec 'Journey Progress
# Cards' + 'Journey UI Regression Contract' gate scenario).


@pytest.mark.asyncio
async def test_journey_achievements_surface(client):
    """Journey must ship #achievements-card immediately after #momentum-card
    (gate scenario: '#achievements-card' found after '#momentum-card'); app.js
    must define renderAchievements, destructure newAchievementKeys from
    WeightFormat, keep the prior earned-key set (prevAchievementKeys), diff
    only successful reads (card-scoped failure copy), and render no partial
    progress; format.js must export newAchievementKeys; the new CSS must be
    token-only with reduced-motion neutralization (spec 'Journey UI
    Regression Contract')."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    journey = html[html.index('id="tab-journey"') : html.index('id="tab-world"')]
    # The achievements card ships inside the Journey panel, after momentum and
    # before quest history (design: insert after #momentum-card).
    assert 'id="achievements-card"' in journey
    assert (
        journey.index('id="momentum-card"')
        < journey.index('id="achievements-card"')
        < journey.index('id="quest-history-card"')
    ), "#achievements-card must sit between #momentum-card and #quest-history-card"
    assert 'aria-label="Achievements"' in journey

    fmt = await client.get("/static/format.js")
    assert fmt.status_code == 200
    assert "function newAchievementKeys" in fmt.text, (
        "format.js must define newAchievementKeys()"
    )
    assert re.search(
        r"milestoneNextLabel,\s*newAchievementKeys", fmt.text
    ) is not None, (
        "newAchievementKeys must be registered on the format.js api export"
    )

    app = await client.get("/static/app.js")
    assert app.status_code == 200
    body = app.text
    assert "function renderAchievements" in body, (
        "app.js must define renderAchievements()"
    )
    assert re.search(
        r"\{[^}]*newAchievementKeys[^}]*\}\s*=\s*globalThis\.WeightFormat", body
    ) is not None, "app.js must destructure newAchievementKeys from WeightFormat"
    # Read-diff state + wiring: prior earned-key set kept, diff consulted, and
    # the achievements fetch added beside momentum (Promise.allSettled batch).
    assert "let prevAchievementKeys = null" in body
    assert "newAchievementKeys(" in body
    assert re.search(r"fetchJson\(\"/api/achievements\"\)", body) is not None, (
        "app.js must fetch /api/achievements"
    )
    # Failure is card-scoped: the achievements error copy must exist, and the
    # prior set must only be re-stored on a fulfilled read (never on failure).
    assert "Could not load achievements" in body
    # Locked rows render without partial progress (no progress elements).
    assert "achievement-progress" not in body

    css = await client.get("/static/style.css")
    assert css.status_code == 200
    sheet = css.text
    assert re.search(r"\.achievements-card\s*\{", sheet) is not None, (
        "style.css must declare a .achievements-card rule"
    )
    # Token-only: the new surface rules must not introduce palette hex.
    achievement_rules = list(re.finditer(r"\.achievement[a-z-]*\s*\{[^}]*}", sheet))
    assert len(achievement_rules) > 0, "style.css must declare achievement rules"
    for rule in achievement_rules:
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0)) is None, (
            "achievement CSS must be token-only (no hex literals)"
        )
    # Reduced motion: the new card's transition is neutralized.
    media_at = sheet.index("@media (prefers-reduced-motion: reduce)")
    block = sheet[media_at:]
    assert re.search(
        r"\.achievements-card[^}]*transition\s*:\s*none", block
    ), "reduced-motion must neutralize .achievements-card"


# ---- r2-world-xp-island S3 gate additions (PR 3): live island wiring ------
# app.js must ship the runtime wiring the static S2 island needs: renderWorld()
# defined, worldStage destructured from the format.js api, the transient
# prevWorldStage read-diff state, and stageChanged invoked inside the fulfilled
# /api/xp branch of loadQuestsAndXp() — not merely somewhere in app.js. Stage
# math and diff eligibility are pinned by tests/frontend/world.test.mjs and the
# behavior by tests/smoke-ui.sh; these gate the delivered artifacts (design
# §SPA; spec 'Stage-Up Celebration').


def _js_block(source: str, brace_at: int) -> str:
    """Return the brace-delimited block starting at the `{` at brace_at
    (including both braces), treating strings and comments as opaque so
    braces inside template literals never confuse the depth count."""
    assert source[brace_at] == "{"
    depth = 0
    i = brace_at
    n = len(source)
    quote = None  # None, "'", '"', or '`'
    while i < n:
        c = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if quote is not None:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in ("'", '"', "`"):
            quote = c
        elif c == "/" and nxt == "/":
            newline = source.find("\n", i)
            if newline == -1:
                break
            i = newline
        elif c == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            if end == -1:
                break
            i = end + 2
            continue
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return source[brace_at : i + 1]
        i += 1
    raise AssertionError("unbalanced braces in JS block")


def _js_fn_body(source: str, name: str) -> str:
    """Return the brace-delimited body of the named function in the served JS
    (including the outer braces), so scoped assertions can never bleed into a
    later top-level function."""
    m = re.search(
        rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)", source
    )
    assert m is not None, f"app.js must define {name}()"
    return _js_block(source, source.index("{", m.end()))


@pytest.mark.asyncio
async def test_app_js_ships_world_island_runtime_wiring(client):
    """app.js must define renderWorld(), destructure worldStage from
    WeightFormat, keep the transient prevWorldStage read-diff state, and invoke
    stageChanged inside the fulfilled /api/xp branch of loadQuestsAndXp() — the
    stage-up celebration must be wired where successful XP reads land, not
    merely anywhere in app.js (design §SPA; spec 'Stage-Up Celebration')."""
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "function renderWorld" in body, "app.js must define renderWorld()"
    assert re.search(
        r"\{[^}]*worldStage[^}]*\}\s*=\s*globalThis\.WeightFormat", body
    ) is not None, "app.js must destructure worldStage from WeightFormat"
    assert "let prevWorldStage = null" in body, (
        "app.js must keep transient prevWorldStage read-diff state"
    )
    # The stageChanged read-diff must sit inside the fulfilled /api/xp branch
    # of loadQuestsAndXp(), not merely somewhere in app.js: extract the
    # function and check the call lands inside the xpRes fulfilled branch.
    fn = _js_fn_body(body, "loadQuestsAndXp")
    branch_at = re.search(r'if \(xpRes\.status === "fulfilled"\)\s*\{', fn)
    assert branch_at is not None, (
        "loadQuestsAndXp() must branch on xpRes.status === 'fulfilled'"
    )
    branch = _js_block(fn, branch_at.end() - 1)
    assert "stageChanged(" in branch, (
        "loadQuestsAndXp() must invoke stageChanged() inside the fulfilled "
        "/api/xp branch"
    )

# ---- r2-completion S1 gate additions (quest-icons spec R1/R4) ------------
# The format.js QUEST_DOMAIN_ICONS array-of-pairs literal (ast.literal_eval
# drift-guard, mirroring the EXERCISE_TYPES/HABIT_TYPES convention) pins the
# nine-domain catalogue and the six stored QUEST_POOL subset; the app.js
# renderers place the decorative icon via iconForDomain with aria-hidden.

_QUEST_ICON_DOMAINS = (
    "exercise", "nutrition", "movement", "routine", "wellbeing",
    "weight", "strength", "sleep", "recovery",
)


@pytest.mark.asyncio
async def test_format_js_ships_quest_domain_icons_drift_guard(client):
    resp = await client.get("/static/format.js")
    assert resp.status_code == 200
    body = resp.text
    match = re.search(
        r"QUEST_DOMAIN_ICONS\s*=\s*(\[\s*\[[^\]]*\]\s*(?:,\s*\[[^\]]*\]\s*)*(?:,)?\s*\])",
        body,
    )
    assert match is not None, "format.js must embed the QUEST_DOMAIN_ICONS literal"
    pairs = ast.literal_eval(match.group(1))
    domains = [d for d, _ in pairs]
    assert domains == list(_QUEST_ICON_DOMAINS), f"keys must pin the nine domains: {domains}"
    assert all(svg.strip() and "<svg" in svg and "</svg>" in svg for _, svg in pairs)
    stored = sorted({q[1] for q in QUEST_POOL})
    assert sorted(set(domains) & set(stored)) == stored, (
        f"icons must cover every stored QUEST_POOL domain: {stored}"
    )


@pytest.mark.asyncio
async def test_app_js_quest_renderers_use_decorative_domain_icons(client):
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert re.search(
        r"\{[^}]*iconForDomain[^}]*\}\s*=\s*globalThis\.WeightFormat", body
    ) is not None, "app.js must destructure iconForDomain from WeightFormat"
    for fn_name in ("renderQuests", "renderQuestHistory"):
        fn = _js_fn_body(body, fn_name)
        assert "iconForDomain(" in fn
        assert '"quest-domain-icon"' in fn
        assert 'setAttribute("aria-hidden", "true")' in fn

# ---- r2-completion S3 gate additions (weekly objectives UI) -------------
# Compact slice-3 gates (PR 3): Today #weekly-card (two container-first rows +
# recovery-safe #weekly-error), Journey #weekly-journey-card (status/history),
# app.js weekly allSettled fetch + render hooks + signal seam + no XP copy,
# token-only weekly CSS with mobile + reduced-motion (behavior via smoke).


@pytest.mark.asyncio
async def test_index_html_ships_weekly_surfaces(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    today = html[html.index('id="tab-today"') : html.index('id="tab-journey"')]
    assert 'id="weekly-card"' in today
    assert today.index('id="quests-card"') < today.index('id="weekly-card"')
    card = today[today.index('id="weekly-card"') : today.index("</section>", today.index('id="weekly-card"'))]
    assert "<h2>Weekly objectives</h2>" in card
    assert card.count('class="weekly-progress-row"') == 2
    assert all(g in card for g in ('data-goal="quests"', 'data-goal="good_days"'))
    assert card.count('role="progressbar"') == 2 and card.count("progress-fill") == 2
    assert 'id="weekly-error"' in card
    journey = html[html.index('id="tab-journey"') : html.index('id="tab-world"')]
    assert 'id="weekly-journey-card"' in journey
    assert (journey.index('id="momentum-card"')
            < journey.index('id="weekly-journey-card"')
            < journey.index('id="achievements-card"'))
    assert 'id="weekly-current-status"' in journey and 'id="weekly-history"' in journey


@pytest.mark.asyncio
async def test_app_js_ships_weekly_loading_and_render_hooks(client):
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    fn = _js_fn_body(body, "loadJourneyCards")
    assert "Promise.allSettled" in fn and 'fetchJson("/api/weekly")' in fn
    assert all(f"function {h}" in body for h in ("renderWeekly", "renderWeeklyToday", "renderWeeklyJourney"))
    rw = _js_fn_body(body, "renderWeekly")
    assert "weeklyMetSignals.push(" in rw
    assert '$("weekly-error")' in rw and "err.hidden = false" in rw and "err.hidden = true" in rw
    assert "Could not load weekly objectives" in body
    rt = _js_fn_body(body, "renderWeeklyToday")
    assert re.search(r"Math\.min\(100,\s*Math\.max\(0,", rt) and 'setAttribute("role", "progressbar")' in rt and '"Met"' in rt
    assert "Exempt this week" in rt and "starts Monday in" in rt
    rj = _js_fn_body(body, "renderWeeklyJourney")
    assert re.search(r"exempt \? \"Exempt\"", rj)
    assert "week_start" in rj and re.search(r"\.\.\.[^;]*\.sort\(", rj)
    assert "No completed weeks yet." in rj and all("XP" not in s for s in (rt, rj))
    assert "let weeklyMetSignals = []" in body and '"weekly_met"' in body
    assert "Math.max(0" in _js_fn_body(body, "weeklyDaysUntilMonday")


@pytest.mark.asyncio
async def test_style_css_ships_weekly_rules_token_only(client):
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    sheet = resp.text
    for selector in (".weekly-card", ".weekly-journey-card", ".weekly-progress-row"):
        assert selector in sheet
    rules = list(re.finditer(r"\.weekly-[a-z-]+\s*\{[^}]*}", sheet))
    assert rules and all(re.search(r"#[0-9a-fA-F]{3,8}\b", r.group(0)) is None for r in rules)
    assert re.search(r"\.weekly-progress-header\s*\{[^}]*flex-wrap", sheet[sheet.index("@media (max-width: 480px)"):])
    block = sheet[sheet.index("@media (prefers-reduced-motion: reduce)"):]
    assert re.search(r"\.weekly-card(?![\-\w])[^}]*transition\s*:\s*none", block)
    assert re.search(r"\.weekly-journey-card[^}]*transition\s*:\s*none", block)
    assert re.search(r"\.weekly-progress-row \.progress-fill[^}]*transition\s*:\s*none", block)


# ---- r2-completion S5 gate additions (collectibles UI) ------------------
# The collectibles shelf ships inside Journey after #achievements-card (before
# #quest-history-card), Journey-only (R12) — data-driven rows + scoped error
# slot; the World island SVG ships a hidden default latest-earn accent. app.js
# fetches /api/collectibles in loadJourneyCards' allSettled, keeps
# prevCollectibleKeys, queues collectibleSignals (collectible_first_earn) on
# fulfilled reads, and never clears the shelf on failure. CSS token-only.


@pytest.mark.asyncio
async def test_journey_collectibles_surface(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    journey = html[html.index('id="tab-journey"') : html.index('id="tab-world"')]
    world = html[html.index('id="tab-world"') : html.index('id="tab-me"')]
    # The shelf ships inside Journey, after achievements and before quest
    # history (design: insert after #achievements-card).
    assert 'id="collectibles-card"' in journey
    assert (
        journey.index('id="achievements-card"')
        < journey.index('id="collectibles-card"')
        < journey.index('id="quest-history-card"')
    ), "#collectibles-card must sit between #achievements-card and #quest-history-card"
    assert 'aria-label="Collectibles"' in journey
    # Data-driven rows container + scoped error slot inside the card.
    card = journey[
        journey.index('id="collectibles-card"') : journey.index('id="quest-history-card"')
    ]
    assert 'id="collectibles-list"' in card
    assert 'id="collectibles-error"' in card
    # Shelf is Journey-only (R12): the World panel must not ship the card.
    assert 'id="collectibles-card"' not in world
    # World SVG latest-earn accent: present inside the island, hidden + empty
    # (data-key/aria-label blank) by default.
    island = world[world.index("<svg") : world.index("</svg>") + len("</svg>")]
    assert 'id="world-latest-earn"' in island
    assert re.search(r'id="world-latest-earn"[^>]*\shidden', island) is not None
    assert re.search(r'id="world-latest-earn"[^>]*data-key=""', island) is not None

    app = await client.get("/static/app.js")
    assert app.status_code == 200
    body = app.text
    fn = _js_fn_body(body, "loadJourneyCards")
    assert "Promise.allSettled" in fn and 'fetchJson("/api/collectibles")' in fn
    assert "function renderCollectibles" in body
    # Signal seam: module-level prior-key state + first-earn signal queue.
    assert "let prevCollectibleKeys = null" in body
    assert "let collectibleSignals = []" in body
    assert '"collectible_first_earn"' in body
    # Reuses the shared achievements read-diff helper.
    assert "newAchievementKeys(" in body
    # Card-scoped failure copy that preserves the shelf (static error slot).
    assert "Could not load collectibles" in body
    assert '$("collectibles-error")' in body

    css = await client.get("/static/style.css")
    assert css.status_code == 200
    sheet = css.text
    assert re.search(r"\.collectibles-card\s*\{", sheet) is not None
    # Token-only: collectible + accent rules must not introduce palette hex
    # (ghost-loop guard: materialize matches before asserting).
    collectible_rules = list(re.finditer(r"\.collectible[a-z:-]*\s*\{[^}]*}", sheet))
    assert len(collectible_rules) > 0, "style.css must declare collectible rules"
    for rule in collectible_rules:
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0)) is None, (
            "collectible CSS must be token-only (no hex literals)"
        )
    accent_rules = list(re.finditer(r"\.world-latest-earn[a-z-]*\s*\{[^}]*}", sheet))
    assert len(accent_rules) > 0, "style.css must declare World accent rules"
    for rule in accent_rules:
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0)) is None, (
            "World accent CSS must be token-only (no hex literals)"
        )
    # Mobile (<=480px must not clip) + reduced-motion (card/art/accent static).
    mobile = sheet[sheet.index("@media (max-width: 480px)"):]
    assert re.search(r"\.collectible-row[^}]*flex-wrap", mobile) is not None
    block = sheet[sheet.index("@media (prefers-reduced-motion: reduce)"):]
    assert re.search(r"\.collectibles-card[^}]*transition\s*:\s*none", block) is not None
    assert re.search(r"\.collectible-art[^}]*animation\s*:\s*none", block) is not None
    assert re.search(r"\.world-latest-earn[^}]*animation\s*:\s*none", block) is not None
# ---- r2-completion S6 celebration queue gate (R14-R18) ----------------


@pytest.mark.asyncio
async def test_celebration_queue_surfaces(client):
    html = (await client.get("/")).text
    assert re.search(r'id="celebration-banner"[^>]*\shidden', html)
    fmt = (await client.get("/static/format.js")).text
    for fn in ("questStatusChanged", "weeklyMetDiff", "collectibleKeysetDiff", "enqueueCelebrations"):
        assert f"function {fn}" in fmt
    assert "enqueueCelebrations" in fmt.split("const api =")[1]
    body = (await client.get("/static/app.js")).text
    assert "let prevLevel = null" in body
    # Producers only stage; loadJourneyCards flushes the queue once (R18).
    enq = _js_fn_body(body, "enqueueCelebrationEvents")
    assert "push" in enq and "flushCelebrationQueue" not in enq
    assert "flushCelebrationQueue();" in _js_fn_body(body, "loadJourneyCards")
    fq = _js_fn_body(body, "flushCelebrationQueue")
    assert "enqueueCelebrations(" in fq and "shift()" in fq
    mq = _js_fn_body(body, "mutateQuest")
    assert "res.level_up" in mq
    lq = _js_fn_body(body, "loadQuestsAndXp")
    assert 'xpRes.status === "fulfilled"' in lq and "level_up" in lq
    ra = _js_fn_body(body, "renderAchievements")
    assert "fireConfetti(" not in ra and "enqueueCelebrationEvents(" in ra
    sc = _js_fn_body(body, "showCelebration")
    assert "reducedMotion()" in sc
    assert "show();" in sc  # non-level celebrations must render before their delay
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in body
    sheet = (await client.get("/static/style.css")).text
    for rule in re.finditer(r"\.celebration-banner[a-z-]*\s*\{[^}]*}", sheet):
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0))
    assert re.search(r"\.quest-delight\s*\{", sheet)
    block = sheet[sheet.index("@media (prefers-reduced-motion: reduce)"):]
    assert re.search(r"\.celebration-banner[^}]*transition\s*:\s*none", block)
    assert re.search(r"\.quest-delight[^}]*animation\s*:\s*none", block)


# ---- check-in card (mood + habit quick-log) ------------------------------
# The Today tab ships #checkin-card between #quests-card and #weekly-card:
# a mood scale (five 1-5 buttons, optional note <= 500, submit disabled until
# a valid mood is selected) and a habit quick-log whose chips are rendered by
# app.js FROM the pinned HABIT_TYPES literal (no hardcoded chip HTML). Logging
# posts to /api/mood and /api/habits via fetchJson, refreshes quests+XP on
# success, and keeps section-scoped accessible feedback (role=alert error,
# role=status success). CSS token-only, static (no animation).


@pytest.mark.asyncio
async def test_index_html_ships_checkin_card_between_quests_and_weekly(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    today = html[html.index('id="tab-today"') : html.index('id="tab-journey"')]
    # Strict ordering: quests-card < checkin-card < weekly-card (design: one
    # card, mood first, habit second — never nested cards).
    assert 'id="checkin-card"' in today
    assert (
        today.index('id="quests-card"')
        < today.index('id="checkin-card"')
        < today.index('id="weekly-card"')
    ), "#checkin-card must sit between #quests-card and #weekly-card"
    card = today[today.index('id="checkin-card"') : today.index('id="weekly-card"')]
    assert "<h2>Check in</h2>" in card
    # Mood section first, habit section second.
    assert card.index('id="mood-checkin"') < card.index('id="habit-quicklog"')


@pytest.mark.asyncio
async def test_index_html_ships_mood_scale_1_to_5_and_optional_note(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    card = html[html.index('id="checkin-card"') : html.index('id="weekly-card"')]
    # Five mood buttons, values exactly 1..5 in order, aria-pressed selection
    # semantics inside an accessible group; meaningful per-button labels.
    buttons = re.findall(r'class="checkin-mood"[^>]*data-mood="(\d)"', card)
    assert buttons == ["1", "2", "3", "4", "5"]
    assert len(re.findall(r'aria-pressed="false"', card)) == 5
    assert 'role="group"' in card
    assert 'aria-label="Mood' in card
    # Optional note, hard maxlength 500 matching the server contract.
    assert 'id="mood-note"' in card
    assert 'maxlength="500"' in card
    # Submit starts disabled; only a selected mood enables it. The class that
    # carries the disabled visual lives with the other .checkin-* rules.
    assert 'id="mood-submit"' in card
    assert re.search(r'id="mood-submit"[^>]*class="checkin-submit"[^>]*disabled', card) is not None


@pytest.mark.asyncio
async def test_index_html_habit_chips_are_not_hardcoded(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    card = html[html.index('id="checkin-card"') : html.index('id="weekly-card"')]
    # The habit section ships an EMPTY container; app.js renders the chips
    # from HABIT_TYPES. No hardcoded chip HTML or raw values in the markup.
    assert 'id="habit-chips"' in card
    assert 'class="checkin-habit"' not in card
    for value in ("water", "fruit_veg", "home_cooked", "sleep_routine"):
        assert f'"{value}"' not in card, f"habit value {value} must not be hardcoded in HTML"


@pytest.mark.asyncio
async def test_app_js_renders_habit_chips_from_pinned_literal(client):
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    fn = _js_fn_body(body, "renderHabitChips")
    # The chips are driven by the pinned HABIT_TYPES literal (drift-guard
    # covered by test_habit_types_literal_matches_server_constant): the render
    # loop must iterate the literal and stamp the exact value as data-habit-type.
    assert "HABIT_TYPES" in fn
    assert "data-habit-type" in fn or "habitType" in fn


@pytest.mark.asyncio
async def test_app_js_wires_checkin_posts_and_refresh(client):
    resp = await client.get("/static/app.js")
    assert resp.status_code == 200
    body = resp.text
    # Mood: client guard (validateMood before any fetch), POST /api/mood,
    # pending-disable of mood controls + submit, quests/XP refresh on success.
    mood = _js_fn_body(body, "submitMood")
    assert "validateMood(" in mood
    assert mood.index("validateMood(") < mood.index('fetchJson("/api/mood"')
    assert 'fetchJson("/api/mood"' in mood
    assert "disabled = true" in mood
    assert "loadQuestsAndXp()" in mood
    # Habit: one-tap POST /api/habits, chips disabled while in flight, refresh.
    habit = _js_fn_body(body, "logHabit")
    assert 'fetchJson("/api/habits"' in habit
    assert "disabled = true" in habit
    assert "loadQuestsAndXp()" in habit
    # Both endpoints use the shared same-origin fetch helper with JSON bodies.
    assert re.search(r"headers: \{\s*\"Content-Type\": \"application/json\"", mood) is not None
    assert re.search(r"headers: \{\s*\"Content-Type\": \"application/json\"", habit) is not None


@pytest.mark.asyncio
async def test_index_html_checkin_hints_are_accessible(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    card = html[html.index('id="checkin-card"') : html.index('id="weekly-card"')]
    # Error regions are role=alert; success hints are role=status (aria-live).
    assert 'id="mood-error"' in card and 'role="alert"' in card
    assert 'id="mood-success"' in card and 'role="status"' in card
    assert 'id="habit-error"' in card and 'role="alert"' in card
    assert 'id="habit-success"' in card and 'role="status"' in card


@pytest.mark.asyncio
async def test_style_css_checkin_rules_token_only(client):
    resp = await client.get("/static/style.css")
    assert resp.status_code == 200
    sheet = resp.text
    for selector in (".checkin-card", ".checkin-section", ".checkin-mood", ".checkin-habit", ".checkin-submit"):
        assert selector in sheet, f"style.css must declare {selector}"
    # Token-only: every .checkin-* rule must use semantic tokens, never hex.
    rules = list(re.finditer(r"\.checkin-[a-z-]+\s*\{[^}]*}", sheet))
    assert len(rules) > 0, "style.css must declare checkin rules"
    for rule in rules:
        assert re.search(r"#[0-9a-fA-F]{3,8}\b", rule.group(0)) is None, (
            "checkin CSS must be token-only (no hex literals)"
        )
    # Sections separated by a full-width token border (never a side stripe).
    assert re.search(r"\.checkin-section\s*\+\s*\.checkin-section\s*\{[^}]*border-top", sheet) is not None
    # Disabled submit mirrors the controls: reduced opacity + default cursor,
    # accent fill preserved on hover (base button:hover must not re-enable).
    assert re.search(r"\.checkin-submit:disabled\s*\{[^}]*opacity", sheet) is not None
    assert re.search(r"\.checkin-submit:disabled\s*\{[^}]*cursor:\s*default", sheet) is not None
    assert re.search(r"\.checkin-submit:disabled:hover\s*\{[^}]*var\(--accent\)", sheet) is not None
    # Mood row stays usable on narrow mobile (wrap, no clipping).
    media_at = sheet.index("@media (max-width: 480px)")
    assert re.search(r"\.checkin-mood-row[^}]*flex-wrap", sheet[media_at:]) is not None
