# Python pytest integration harness

Copy-paste-ready integration test scaffolding for any Python project that talks to eMASS.

## What's here

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures: `emass_client`, `reset_emass_state` (autouse), `inject_failure`. |
| `test_emass_integration.py` | Reference tests covering round-trip, partial-batch failure, latency, Prism fallthrough. |
| `docker-compose.yml` | Brings up Prism + emass-mock on localhost:18080. |

## Run it

```bash
# 1. Start the mock + Prism
docker compose up -d

# 2. Run the tests (from this directory)
pip install pytest httpx
pytest -v

# 3. Tear down
docker compose down
```

## Adapt to your project

1. Copy `conftest.py` into your own `tests/` directory (or import from it).
2. Replace the direct `emass_client.put(...)` calls in the reference tests with calls to **your** eMASS client code.
3. Keep the assertions — they cover the shape of responses that real eMASS returns.

The `reset_emass_state` fixture is `autouse=True`, so every test gets a clean slate. If you need state to persist across a test (e.g. testing a multi-step workflow), move the reset to session scope or fire it manually.

## Why you want the harness, not just Prism

Prism alone:
- ✅ validates your outgoing payloads against the OpenAPI spec
- ❌ returns random example data on GET — you cannot assert "what I wrote is what I read"
- ❌ cannot mark one control in a 200-item batch as failed
- ❌ has no way to persistently simulate latency or 5xx across a series of requests

The harness adds all three on top of Prism.
