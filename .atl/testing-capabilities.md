## Testing Capabilities

**Strict TDD Mode**: enabled
**Detected**: 2026-08-02

### Test Runner

- Command: `.venv/bin/python -m pytest` (also `pytest` via venv)
- Framework: pytest 9.1.1 + pytest-asyncio 1.4.0, `asyncio_mode = strict` (pytest.ini)
- Evidence: 37 tests passing in 0.18s; async tests use `@pytest.mark.asyncio`,
  async fixtures use `@pytest_asyncio.fixture`

### Test Layers

| Layer       | Available | Tool                             |
| ----------- | --------- | -------------------------------- |
| Unit        | ✅        | pytest (tests/test_rewards.py, test_weight.py) |
| Integration | ✅        | httpx.ASGITransport in-process (tests/test_api.py, conftest.py client fixture) |
| E2E         | ❌        | —                                |

### Coverage

- Available: ❌ (pytest-cov not installed)
- Command: —

### Quality Tools

| Tool         | Available | Command |
| ------------ | --------- | ------- |
| Linter       | ❌        | —       |
| Type checker | ❌        | —       |
| Formatter    | ❌        | —       |

### Harness Notes (tests/conftest.py)

- `app` fixture: tmp_path SQLite DB + tmp VAPID keys, `start_scheduler=False`
- `client` fixture: `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`
- `stub_push` autouse fixture: monkeypatches `notifications.send_to_all` so no real
  web push is ever sent; records sent payloads for assertions
