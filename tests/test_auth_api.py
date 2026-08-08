"""API integration tests for /api/auth/register|login|logout|me.

These assert the spec's session-cookie behavior end to end through the
httpx ASGITransport harness: registration, duplicate/invalid rejection,
login, identity, revocation, and cookie attributes.
"""

import re

import httpx
import pytest

import routes as routes_module
from auth import generate_session_token, hash_session_token
from constants import SESSION_COOKIE_NAME, SESSION_EXPIRY_SECONDS
from database import run_db


def _session_token(resp: httpx.Response) -> str:
    """Extract the raw session secret from a Set-Cookie header."""
    match = re.search(rf"{SESSION_COOKIE_NAME}=([^;]+)", resp.headers["set-cookie"])
    assert match is not None, "expected a session cookie in the response"
    return match.group(1)


async def _register(
    client: httpx.AsyncClient,
    username: str = "alice",
    password: str = "password123",
) -> httpx.Response:
    return await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "email": f"{username}@example.com",
        },
    )


# ---- registration -------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_lowercased_user_and_session(client):
    resp = await _register(client, username="Alice")
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"  # lowercased
    assert body["email"] == "alice@example.com"  # normalized with the username
    assert body["id"] >= 1
    assert body["created_at"]
    # only public identity fields are returned
    assert "password_hash" not in body
    assert "salt" not in body

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["email"] == "alice@example.com"
    assert me.json()["needs_onboarding"] is True  # fresh account, no flag row


@pytest.mark.asyncio
async def test_register_rejects_short_username(client, app):
    resp = await _register(client, username="ab")
    assert resp.status_code == 422
    count = app.state.db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 0  # no account created
    me = await client.get("/api/auth/me")
    assert me.status_code == 401  # no session established


@pytest.mark.asyncio
async def test_register_rejects_long_username(client):
    resp = await _register(client, username="a" * 33)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_username_with_whitespace(client):
    resp = await _register(client, username="ali ce")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_short_password(client):
    resp = await _register(client, password="short")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_unknown_fields(client):
    resp = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "admin": True},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_duplicate_username_conflicts_case_insensitively(
    client, app
):
    first = await _register(client, username="alice")
    assert first.status_code == 201
    second = await _register(client, username="ALICE")
    assert second.status_code == 409
    count = app.state.db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 1  # no second account created


# ---- session cookie security -------------------------------------------


@pytest.mark.asyncio
async def test_session_cookie_carries_secure_attributes(client):
    resp = await _register(client)
    header = resp.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "SameSite=lax" in header
    assert "Path=/" in header
    assert f"Max-Age={SESSION_EXPIRY_SECONDS}" in header
    # Secure off by default so local HTTP development works
    assert "Secure" not in header


@pytest.mark.asyncio
async def test_session_cookie_secure_flag_follows_configuration(
    client, monkeypatch
):
    monkeypatch.setattr(routes_module, "SESSION_COOKIE_SECURE", True)
    resp = await _register(client)
    assert "Secure" in resp.headers["set-cookie"]


@pytest.mark.asyncio
async def test_session_persists_only_the_token_hash(client, app):
    resp = await _register(client)
    token = _session_token(resp)
    rows = app.state.db.conn.execute(
        "SELECT token_hash, user_id FROM sessions"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["token_hash"] == hash_session_token(token)
    assert rows[0]["token_hash"] != token  # raw secret never persisted
    assert rows[0]["user_id"] == resp.json()["id"]


# ---- login / me ---------------------------------------------------------


@pytest.mark.asyncio
async def test_login_then_me_round_trip(client):
    await _register(client)
    await client.post("/api/auth/logout")  # drop the register session
    resp = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
    assert "password_hash" not in resp.json()

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["needs_onboarding"] is True  # fresh account, no flag row


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401(client):
    resp = await client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "password123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    await _register(client)
    await client.post("/api/auth/logout")  # drop the register session
    resp = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "wrong-password"},
    )
    assert resp.status_code == 401
    me = await client.get("/api/auth/me")
    assert me.status_code == 401  # failed login established no session


@pytest.mark.asyncio
async def test_me_without_session_is_401(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


# ---- logout -------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_revokes_the_session(client):
    await _register(client)
    assert (await client.get("/api/auth/me")).status_code == 200

    out = await client.post("/api/auth/logout")
    assert out.status_code == 200

    # the revoked session must be rejected on reuse
    me = await client.get("/api/auth/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_logout_requires_a_valid_session(client):
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_deletes_the_session_row(client, app):
    await _register(client)
    await client.post("/api/auth/logout")
    remaining = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM sessions"
    ).fetchone()[0]
    assert remaining == 0


# ---- expiry -------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_session_is_rejected(client, app):
    """A session row past its expiry must not authenticate — even when the
    cookie is presented. The user and expired session are planted directly
    so no valid session ever exists in the client jar."""
    user = await run_db(app.state.db.create_user, "alice", "hash", "salt")
    expired_token = generate_session_token()
    await run_db(
        app.state.db.create_session,
        user.id,
        hash_session_token(expired_token),
        "2020-01-01 00:00:00",
    )
    client.cookies.set(
        SESSION_COOKIE_NAME, expired_token, domain="test", path="/"
    )
    me = await client.get("/api/auth/me")
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_register_establishes_distinct_session_per_user(client):
    first = await _register(client, username="alice")
    second = await _register(client, username="bob")
    # both users are simultaneously authenticated on the same client jar
    me_first = await client.get("/api/auth/me")
    assert me_first.status_code == 200
    assert me_first.json()["username"] == "bob"  # latest cookie wins
    assert first.json()["id"] != second.json()["id"]

# ---- needs_onboarding flag -------------------------------------------------


@pytest.mark.asyncio
async def test_me_needs_onboarding_true_for_bare_user(client):
    """Spec: a new account with no onboarding_complete row reports true."""
    await _register(client)
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["needs_onboarding"] is True


@pytest.mark.asyncio
async def test_me_needs_onboarding_false_after_completion(client):
    """Spec: completing onboarding flips the flag to false."""
    await _register(client)
    resp = await client.post(
        "/api/onboarding",
        json={"height_cm": 175.0, "weight_kg": 80.0, "target_weight": 70.0},
    )
    assert resp.status_code == 200, resp.text
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["needs_onboarding"] is False


@pytest.mark.asyncio
async def test_me_needs_onboarding_true_for_preexisting_account(client, app):
    """Spec: accounts created before this change have no onboarding_complete
    row, so their next /me surfaces the wizard once."""
    user = await run_db(app.state.db.create_user, "legacy", "hash", "salt")
    token = generate_session_token()
    await run_db(
        app.state.db.create_session,
        user.id,
        hash_session_token(token),
        "2099-01-01 00:00:00",
    )
    client.cookies.set(SESSION_COOKIE_NAME, token, path="/")
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "legacy"
    assert me.json()["needs_onboarding"] is True
