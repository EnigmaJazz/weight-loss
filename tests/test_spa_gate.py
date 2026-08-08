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

from constants import EXERCISE_TYPES


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
async def test_index_html_ships_onboarding_wizard_between_auth_and_tracker(client):
    """The onboarding wizard ships in the delivered HTML, starts hidden, sits
    between the auth gate and the tracker, and carries all five step blocks
    plus the target mode toggle and schedule fields the wizard submits."""
    resp = await client.get("/")
    assert resp.status_code == 200
    html = resp.text
    auth_at = html.find('id="auth-screen"')
    wizard_at = html.find('id="onboarding-screen"')
    tracker_at = html.find('id="tracker"')
    assert wizard_at != -1, "index.html must ship the onboarding screen"
    assert auth_at != -1 and tracker_at != -1 and auth_at < wizard_at < tracker_at
    assert 'id="onboarding-screen" hidden' in html
    # All five wizard steps ship, in order: height -> weight -> target ->
    # units -> notifications.
    for step_id in (
        "wizard-step-height",
        "wizard-step-weight",
        "wizard-step-target",
        "wizard-step-units",
        "wizard-step-notifications",
    ):
        assert f'id="{step_id}"' in html
    assert (
        html.find('id="wizard-step-height"')
        < html.find('id="wizard-step-weight"')
        < html.find('id="wizard-step-target"')
        < html.find('id="wizard-step-units"')
        < html.find('id="wizard-step-notifications"')
    )
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
    the onboarding screen a 5-dot wizard indicator with no visible text
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
    assert dots == ["height", "weight", "target", "units", "notifications"], (
        "wizard indicator must carry the five step dots, in order, text-free"
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
