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
