"""Shared test harness: temp-DB app without a scheduler, stubbed push sending."""

import os
from typing import Iterable

# The live deployment sets WEIGHT_LOSS_COOKIE_SECURE=true in .env so the
# session cookie carries the Secure flag over HTTPS. httpx test clients talk
# plain http://test, where a Secure cookie is silently dropped and every
# authenticated request would 401. Force the flag off for tests regardless of
# .env (dotenv does not override an already-set env var), keeping the harness
# deterministic.
os.environ["WEIGHT_LOSS_COOKIE_SECURE"] = ""

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import notifications as notifications_module
from database import Database
from main import create_app, init_app_state
from models import PushSubscription, User
from py_vapid import Vapid

DEFAULT_PASSWORD = "password123"
AUTH_USERNAME = "tester"  # the username the auth_client fixture registers


@pytest_asyncio.fixture
async def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    yield app


@pytest_asyncio.fixture
async def client(app):
    """Bare client with no session cookie — for auth-flow and 401 tests."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(app):
    """Client already registered + logged in as a fresh user (fresh per-test DB,
    so the fixed username never collides). Protected-endpoint tests use this."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/register",
            json={
                "username": AUTH_USERNAME,
                "password": DEFAULT_PASSWORD,
                "email": f"{AUTH_USERNAME}@example.com",
            },
        )
        assert resp.status_code == 201, resp.text
        yield ac


@pytest_asyncio.fixture
async def pair(app):
    """Two authenticated clients (alice, bob) on the same app for isolation
    tests: each registers its own account, so each owns an independent session."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as alice, httpx.AsyncClient(transport=transport, base_url="http://test") as bob:
        await register_user(alice, "alice")
        await register_user(bob, "bob")
        yield alice, bob


async def register_user(
    client: httpx.AsyncClient, username: str, password: str = DEFAULT_PASSWORD
) -> int:
    """Register a user through the API; returns the new user's id."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "email": f"{username}@example.com",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def auth_user_id(app: FastAPI) -> int:
    """The user id of the account the auth_client fixture registered."""
    user = app.state.db.get_user_by_username(AUTH_USERNAME)
    assert user is not None
    return user.id


def make_user(db: Database, username: str = "user") -> User:
    """Create a user directly in the DB (no API, no scrypt); returns the User."""
    return db.create_user(username, "hash", "salt")


@pytest.fixture(autouse=True)
def stub_push(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Never send a real web push in tests; record calls for assertions."""
    sent: list[dict[str, str]] = []

    async def fake_send_to_all(
        subscriptions: Iterable[PushSubscription],
        title: str,
        body: str,
        vapid: Vapid,
        notif_type: str = "test",
    ) -> int:
        count = 0
        for sub in subscriptions:
            sent.append(
                {"endpoint": sub.endpoint, "title": title, "body": body, "notif_type": notif_type}
            )
            count += 1
        return count

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)
    return sent
