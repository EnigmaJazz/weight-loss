"""Shared test harness: temp-DB app without a scheduler, stubbed push sending."""

import httpx
import pytest
import pytest_asyncio

import notifications as notifications_module
from main import create_app, init_app_state


@pytest_asyncio.fixture
async def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    vapid_path = str(tmp_path / "vapid_keys.json")
    app = create_app(db_path=db_path, vapid_path=vapid_path, start_scheduler=False)
    init_app_state(app, db_path=db_path, vapid_path=vapid_path)
    yield app


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def stub_push(monkeypatch):
    """Never send a real web push in tests; record calls for assertions."""
    sent: list = []

    async def fake_send_to_all(subscriptions, title, body, vapid, notif_type="test"):
        count = 0
        for sub in subscriptions:
            sent.append(
                {"endpoint": sub.endpoint, "title": title, "body": body}
            )
            count += 1
        return count

    monkeypatch.setattr(notifications_module, "send_to_all", fake_send_to_all)
    return sent
