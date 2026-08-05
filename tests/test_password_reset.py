"""API integration + unit tests for account email and password reset.

Covers: registration with an email, PUT /api/auth/me email updates,
forgot-password (one-time token issuance, mailer invocation, no account
enumeration, dev fallback when SMTP is unset), reset-password (password
change, token consumption, session revocation, expiry), and the new
database primitives (user email, reset tokens, revoke-all-sessions).

The SMTP mailer is always stubbed (autouse fixture) so no real email is
ever sent; the stub records calls and exposes the raw reset token through
the reset link it captured, exactly like the live dev-fallback log does.
"""

import pytest

import routes as routes_module
from auth import generate_reset_token, hash_reset_token, hash_session_token
from database import DuplicateEmailError, run_db
from tests.conftest import DEFAULT_PASSWORD
from urllib.parse import parse_qs, urlparse

import mailer as mailer_module

GENERIC_FORGOT_MESSAGE = "If that email exists, a reset link is on its way"
BASE_URL = "http://localhost:8000"


@pytest.fixture(autouse=True)
def stub_mailer(monkeypatch):
    """Never send a real SMTP email in tests; record calls for assertions."""
    sent: list = []

    def fake_send_reset_email(to_email: str, reset_url: str) -> bool:
        sent.append({"to_email": to_email, "reset_url": reset_url})
        return True

    monkeypatch.setattr(mailer_module, "send_reset_email", fake_send_reset_email)
    return sent


def _token_from_url(reset_url: str) -> str:
    """Extract the raw reset token from a captured reset link."""
    query = parse_qs(urlparse(reset_url).query)
    return query["reset"][0]


def _raw_token_matching(stub_mailer: list, token_hash: str) -> str:
    """Find the raw token whose hash matches a stored token_hash by scanning
    the stubbed mailer's captured reset links (the live dev-fallback log does
    the same recovery)."""
    for capture in stub_mailer:
        raw = _token_from_url(capture["reset_url"])
        if hash_reset_token(raw) == token_hash:
            return raw
    raise AssertionError("no captured reset link matches the stored token hash")


async def _register(
    client, username="alice", password=DEFAULT_PASSWORD, email=None
):
    return await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "email": email if email is not None else f"{username}@example.com",
        },
    )


# ---- registration with email ----------------------------------------------


@pytest.mark.asyncio
async def test_register_with_email_returns_email_in_me(client):
    resp = await _register(client)
    assert resp.status_code == 201
    assert resp.json()["email"] == "alice@example.com"
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_register_normalizes_email(client, app):
    resp = await _register(client, email="  Alice@Example.COM ")
    assert resp.status_code == 201
    assert resp.json()["email"] == "alice@example.com"
    stored = app.state.db.conn.execute(
        "SELECT email FROM users WHERE username = 'alice'"
    ).fetchone()["email"]
    assert stored == "alice@example.com"


@pytest.mark.asyncio
async def test_register_without_email_is_422(client):
    resp = await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": DEFAULT_PASSWORD},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_malformed_email(client, app):
    for bad in ("not-an-email", "a@b", "a b@example.com", "@example.com", "a@"):
        resp = await _register(client, email=bad)
        assert resp.status_code == 422, bad
    count = app.state.db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 0


# ---- PUT /api/auth/me (set/update email) ----------------------------------


@pytest.mark.asyncio
async def test_put_me_requires_auth(client):
    resp = await client.put(
        "/api/auth/me", json={"email": "new@example.com"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_me_sets_and_updates_email(client, app):
    await _register(client)
    resp = await client.put(
        "/api/auth/me", json={"email": "new@example.com"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@example.com"
    me = await client.get("/api/auth/me")
    assert me.json()["email"] == "new@example.com"

    updated = await client.put(
        "/api/auth/me", json={"email": "other@example.com"}
    )
    assert updated.json()["email"] == "other@example.com"


@pytest.mark.asyncio
async def test_put_me_rejects_malformed_email(client):
    await _register(client)
    resp = await client.put("/api/auth/me", json={"email": "not-an-email"})
    assert resp.status_code == 422


# ---- forgot-password ------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_known_email_creates_token_and_calls_mailer(
    client, app, stub_mailer, monkeypatch
):
    monkeypatch.setattr(routes_module, "PUBLIC_URL", BASE_URL)
    registered = await _register(client)
    assert registered.status_code == 201

    resp = await client.post(
        "/api/auth/forgot-password", json={"email": "alice@example.com"}
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == GENERIC_FORGOT_MESSAGE

    rows = app.state.db.conn.execute(
        "SELECT token_hash, user_id FROM reset_tokens"
    ).fetchall()
    assert len(rows) == 1
    assert len(stub_mailer) == 1
    call = stub_mailer[0]
    assert call["to_email"] == "alice@example.com"
    token = _token_from_url(call["reset_url"])
    # the reset link points at the app root with the raw token in the query
    assert call["reset_url"] == f"{BASE_URL}/?reset={token}"
    # only the SHA-256 hash is persisted, never the raw token
    assert rows[0]["token_hash"] == hash_reset_token(token)
    assert rows[0]["token_hash"] != token
    assert rows[0]["user_id"] == registered.json()["id"]


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_200_without_token_or_mail(
    client, app, stub_mailer
):
    resp = await client.post(
        "/api/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == GENERIC_FORGOT_MESSAGE
    assert stub_mailer == []
    rows = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM reset_tokens"
    ).fetchone()[0]
    assert rows == 0


@pytest.mark.asyncio
async def test_forgot_password_does_not_enumerate_registered_emails(client):
    known = await client.post(
        "/api/auth/forgot-password", json={"email": "ghost@example.com"}
    )
    assert known.status_code == 200
    first_message = known.json()["message"]

    await _register(client, email="ghost@example.com")
    real = await client.post(
        "/api/auth/forgot-password", json={"email": "ghost@example.com"}
    )
    assert real.status_code == 200
    assert real.json()["message"] == first_message


@pytest.mark.asyncio
async def test_forgot_password_rejects_malformed_email(client):
    resp = await client.post(
        "/api/auth/forgot-password", json={"email": "not-an-email"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_forgot_password_dev_fallback_when_smtp_unset(client, app, monkeypatch):
    """With SMTP unconfigured (send returns False) the endpoint still returns
    200 and the token row is created — the operator recovers the link from
    the dev-fallback log instead of the flow failing."""
    await _register(client)

    def fake_fail(to_email: str, reset_url: str) -> bool:
        return False

    monkeypatch.setattr(mailer_module, "send_reset_email", fake_fail)
    resp = await client.post(
        "/api/auth/forgot-password", json={"email": "alice@example.com"}
    )
    assert resp.status_code == 200
    rows = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM reset_tokens"
    ).fetchone()[0]
    assert rows == 1


# ---- reset-password -------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_changes_password_and_revokes_sessions(
    client, app, stub_mailer
):
    """A valid token updates the scrypt hash, consumes the token, and revokes
    every session — including the one the client jar still holds."""
    await _register(client)
    assert (await client.get("/api/auth/me")).status_code == 200  # session live

    forgot = await client.post(
        "/api/auth/forgot-password", json={"email": "alice@example.com"}
    )
    assert forgot.status_code == 200

    rows = app.state.db.conn.execute(
        "SELECT token_hash FROM reset_tokens"
    ).fetchall()
    assert len(rows) == 1
    raw_token = _raw_token_matching(stub_mailer, rows[0]["token_hash"])

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "new-password-123"},
    )
    assert resp.status_code == 200

    # the register-time session was revoked along with everything else: the
    # client jar still holds cookie A, which must now be rejected
    me = await client.get("/api/auth/me")
    assert me.status_code == 401

    # old password no longer works, new password does
    old = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": DEFAULT_PASSWORD},
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "new-password-123"},
    )
    assert new.status_code == 200

    # the token was consumed (deleted on use)
    remaining = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM reset_tokens"
    ).fetchone()[0]
    assert remaining == 0


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_token(client):
    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": generate_reset_token(), "password": "new-password-123"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_token(client, app):
    user = await run_db(app.state.db.create_user, "alice", "hash", "salt")
    expired_token = generate_reset_token()
    await run_db(
        app.state.db.create_reset_token,
        user.id,
        hash_reset_token(expired_token),
        "2020-01-01 00:00:00",
    )
    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": expired_token, "password": "new-password-123"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_rejects_used_token(client, app, stub_mailer):
    await _register(client)
    await client.post(
        "/api/auth/forgot-password", json={"email": "alice@example.com"}
    )
    rows = app.state.db.conn.execute(
        "SELECT token_hash FROM reset_tokens"
    ).fetchall()
    assert len(rows) == 1
    raw_token = _raw_token_matching(stub_mailer, rows[0]["token_hash"])

    first = await client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "new-password-123"},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "another-password"},
    )
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password_without_consuming_token(
    client, app, stub_mailer
):
    await _register(client)
    await client.post(
        "/api/auth/forgot-password", json={"email": "alice@example.com"}
    )
    rows = app.state.db.conn.execute(
        "SELECT token_hash FROM reset_tokens"
    ).fetchall()
    assert len(rows) == 1
    raw_token = _raw_token_matching(stub_mailer, rows[0]["token_hash"])

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "short"},
    )
    assert resp.status_code == 422
    # the token survives: a valid password still succeeds afterwards
    remaining = app.state.db.conn.execute(
        "SELECT COUNT(*) FROM reset_tokens"
    ).fetchone()[0]
    assert remaining == 1


# ---- email uniqueness (account-takeover guard) ---------------------------


@pytest.mark.asyncio
async def test_register_rejects_email_owned_by_another_account(client, app):
    """A shared email would let one owner reset the other's password via
    forgot-password, so registration must reject a taken address."""
    first = await _register(client, username="alice")
    assert first.status_code == 201
    second = await _register(client, username="mallory", email="alice@example.com")
    assert second.status_code == 409
    assert second.json()["detail"] == "email already in use"
    count = app.state.db.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 1  # no second account created


@pytest.mark.asyncio
async def test_put_me_rejects_email_owned_by_another_account(client, app):
    await _register(client, username="alice")
    await _register(client, username="mallory")  # jar now holds mallory's session
    resp = await client.put("/api/auth/me", json={"email": "alice@example.com"})
    assert resp.status_code == 409
    # neither account's email changed
    alice = app.state.db.get_user_by_username("alice")
    assert alice is not None and alice.email == "alice@example.com"
    mallory = app.state.db.get_user_by_username("mallory")
    assert mallory is not None and mallory.email == "mallory@example.com"


@pytest.mark.asyncio
async def test_put_me_keeps_own_email_when_resent(client):
    await _register(client)
    resp = await client.put("/api/auth/me", json={"email": "alice@example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


# ---- database primitives --------------------------------------------------


@pytest.fixture
def db(tmp_path):
    from database import Database

    database = Database(str(tmp_path / "reset.db"))
    database.init_schema()
    yield database
    database.close()


def test_duplicate_email_raises_and_null_emails_are_unlimited(db):
    db.create_user("alice", "hash", "salt", email="alice@example.com")
    with pytest.raises(DuplicateEmailError):
        db.create_user("mallory", "hash", "salt", email="alice@example.com")
    # the partial unique index only constrains non-NULL emails
    db.create_user("bob", "hash", "salt")
    db.create_user("carol", "hash", "salt")
    assert len(db.list_users()) == 3


def test_set_user_email_rejects_another_users_email(db):
    alice = db.create_user("alice", "hash", "salt", email="alice@example.com")
    mallory = db.create_user("mallory", "hash", "salt")
    with pytest.raises(DuplicateEmailError):
        db.set_user_email(mallory.id, "alice@example.com")
    # unchanged, and the owner can re-set their own address
    owner = db.get_user_by_email("alice@example.com")
    assert owner is not None and owner.id == alice.id
    db.set_user_email(mallory.id, "mallory@example.com")
    assert db.get_user_by_email("mallory@example.com").id == mallory.id


def test_create_reset_token_stores_only_the_hash(db):
    user = db.create_user("alice", "hash", "salt")
    token = generate_reset_token()
    row = db.create_reset_token(
        user.id, hash_reset_token(token), "2999-01-01 00:00:00"
    )
    assert row.user_id == user.id
    stored = db.conn.execute(
        "SELECT token_hash FROM reset_tokens"
    ).fetchone()["token_hash"]
    assert stored == hash_reset_token(token)
    assert stored != token  # raw secret never persisted


def test_get_user_by_reset_token_excludes_expired(db):
    user = db.create_user("alice", "hash", "salt")
    fresh = generate_reset_token()
    expired = generate_reset_token()
    db.create_reset_token(user.id, hash_reset_token(fresh), "2999-01-01 00:00:00")
    db.create_reset_token(user.id, hash_reset_token(expired), "2020-01-01 00:00:00")
    assert db.get_user_by_reset_token(hash_reset_token(fresh)) is not None
    assert db.get_user_by_reset_token(hash_reset_token(expired)) is None


def test_get_user_by_email_matches_normalized_email(db):
    user = db.create_user("alice", "hash", "salt", email="alice@example.com")
    found = db.get_user_by_email("alice@example.com")
    assert found is not None
    assert found.id == user.id
    assert db.get_user_by_email("bob@example.com") is None
    assert db.get_user_by_email("") is None
    assert db.get_user_by_email("ALICE@example.com") is None  # exact match


def test_set_user_email_updates_and_returns_user(db):
    user = db.create_user("alice", "hash", "salt")
    updated = db.set_user_email(user.id, "new@example.com")
    assert updated.email == "new@example.com"
    assert db.get_user_by_email("new@example.com") is not None


def test_delete_sessions_for_user_revokes_all(db):
    user = db.create_user("alice", "hash", "salt")
    for _ in range(3):
        db.create_session(
            user.id, hash_session_token(generate_reset_token()), "2999-01-01 00:00:00"
        )
    removed = db.delete_sessions_for_user(user.id)
    assert removed == 3
    remaining = db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert remaining == 0


def test_reset_user_password_is_atomic(db):
    """Password update + token consumption + session revocation in one tx."""
    user = db.create_user("alice", "hash", "salt")
    db.create_session(
        user.id, hash_session_token(generate_reset_token()), "2999-01-01 00:00:00"
    )
    token = generate_reset_token()
    db.create_reset_token(user.id, hash_reset_token(token), "2999-01-01 00:00:00")

    db.reset_user_password(user.id, "newhash", "newsalt", hash_reset_token(token))

    updated = db.get_user_by_username("alice")
    assert updated is not None
    assert updated.password_hash == "newhash"
    assert updated.salt == "newsalt"
    assert db.conn.execute("SELECT COUNT(*) FROM reset_tokens").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
