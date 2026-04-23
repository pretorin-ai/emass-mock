# emass-mock

**A stateful test harness for eMASS integrations.** Built on top of MITRE's official [eMASS OpenAPI spec](https://github.com/mitre/emass_client) and [Stoplight Prism](https://github.com/stoplightio/prism) — adds the pieces Prism alone can't give you: deterministic round-tripping, per-item failure injection, and a copy-paste pytest harness.

> **Not affiliated with the U.S. Department of Defense, DISA, or MITRE.** Independent project. Do not point this at production data.

## The pitch

If you're writing code that pushes to eMASS, you already know Stoplight Prism exists. It serves MITRE's OpenAPI spec as a mock and validates your outgoing payloads. That's great for unit-testing your serializer.

It is **not enough** to test a real integration, because:

- Prism is **stateless.** PUT a control, GET it back, you receive random fake data unrelated to what you pushed. You can't assert `assert control.status == "Planned"` after a write.
- Prism returns **one status per request.** Real eMASS returns mixed success/failure rows within a single batch response — your partial-failure handling code cannot be tested against it.
- Prism has no **idempotency semantics.** Retry logic is untestable.

This harness sits in front of Prism and intercepts the endpoints that need state. For everything else, it proxies to Prism and you inherit spec conformance for free.

## Value pillars

| Pillar | What it unlocks | Prism alone? |
|--------|-----------------|--------------|
| **1. Deterministic round-tripping** | `assert what_i_wrote == what_i_read` on controls, POA&Ms, test results, artifacts. | ❌ |
| **2. Orchestrated failure injection** | Per-control failures inside a batch. Global 5xx. Latency. Recoverable between tests. | ❌ |
| **3. Pytest harness starter kit** | Drop-in fixtures + reference tests. Clone, adapt, done. | ❌ |
| **(Inherited)** Spec-conformant example responses for dashboards, workflows, CMMC, etc. | ✅ via Prism proxy |

## Architecture

```
your code
    │
    │ (api-key, user-uid)
    ▼
┌─────────────────────────────────────────┐
│  emass-mock  :8080                      │
│                                         │
│  ┌──────────────┐   ┌─────────────────┐ │
│  │ State store  │   │ Failure inject. │ │
│  └──────────────┘   └─────────────────┘ │
│                                         │
│  Stateful handlers:                     │
│    PUT  /api/systems/{id}/controls      │
│    POST /api/systems/{id}/test-results  │
│    POST /api/systems/{id}/artifacts     │
│    POST /api/systems/{id}/poams         │
│    GET  /api/systems*                   │
│                                         │
│  Everything else  ──►  Prism            │
└──────────────────────┬──────────────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  Stoplight Prism    │
            │  :4010 (internal)   │
            │                     │
            │  vendor/emass_client│
            │   /eMASSRestOpenApi │
            │   .yaml             │
            └─────────────────────┘
```

## Quick start

```bash
docker compose up -d
curl -H "api-key: test-api-key" -H "user-uid: me" http://localhost:8080/api/systems
# → {"meta":{"code":200},"data":[{"systemId":1,...},...]}

# Round-trip test
curl -X PUT http://localhost:8080/api/systems/1/controls \
     -H "api-key: test-api-key" -H "user-uid: me" \
     -H "content-type: application/json" \
     -d '[{"acronym":"AC-2","responsibleEntities":"System Owner","controlDesignation":"System-Specific","estimatedCompletionDate":1799644800,"implementationNarrative":"AC-2 implementation narrative","implementationStatus":"Planned","slcmCriticality":"Moderate","slcmFrequency":"Quarterly","slcmMethod":"Manual","slcmReporting":"Tracked in Pretorin","slcmTracking":"Tracked in Pretorin","slcmComments":"Tracked in Pretorin"}]'

curl -H "api-key: test-api-key" -H "user-uid: me" http://localhost:8080/api/systems/1/controls
# → {"meta":{"code":200},"data":[{"acronym":"AC-2",...}]}  — same data back
```

Open http://localhost:8080/ui/ for the inspector, http://localhost:8080/docs for OpenAPI of the harness's own surface.

## Using it as a test harness (the main path)

See [`examples/python-pytest/`](examples/python-pytest/) for a ready-to-copy pytest setup. The short version:

```python
# in your conftest.py
import httpx, pytest

@pytest.fixture
def emass(): return httpx.Client(
    base_url="http://localhost:8080",
    headers={"api-key": "test-api-key", "user-uid": "test"},
)

@pytest.fixture(autouse=True)
def reset():
    httpx.post("http://localhost:8080/_admin/reset")
```

```python
# your test
def test_partial_batch_is_handled(emass):
    httpx.post(
        "http://localhost:8080/_admin/failures",
        json={"control_status": {"SC-7": 422}},
    )
    resp = emass.put("/api/systems/1/controls", json=[
        {"acronym": "AC-2"}, {"acronym": "SC-7"},
    ])
    rows = {r["acronym"]: r for r in resp.json()["data"]}
    assert rows["AC-2"]["success"] is True
    assert rows["SC-7"]["success"] is False
```

## Failure injection reference

Admin API (not part of the real eMASS surface):

```bash
# Global 5xx on every request
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" \
     -d '{"global_status": 503}'

# Fail one control in a batch (the other controls still succeed)
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" \
     -d '{"control_status": {"SC-7": 422}}'

# Add latency
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" \
     -d '{"latency_seconds": 2.0}'

# Scope a failure to one path
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" \
     -d '{"path_status": {"/api/systems/1/artifacts": 500}}'

# Reset everything
curl -X POST http://localhost:8080/_admin/reset
```

All above are also available via the inspector UI.

## What's stateful, what proxies to Prism

**Stateful handlers** (the harness persists and replays your data):

- `GET /api/systems`, `GET /api/systems/{id}` — seeded deterministically
- `PUT /api/systems/{id}/controls` + `GET`
- `POST /api/systems/{id}/test-results` + `GET`
- `POST /api/systems/{id}/artifacts` + `GET`
- `POST /api/systems/{id}/poams` + `GET`

**Everything else** (dashboards, workflows, CMMC, baselines, milestones, ...) falls through to Prism, which returns spec-conformant example data. If you hit the harness without `PRISM_URL` set, unhandled paths return `501` with an explanatory message.

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `EMASS_MOCK_HOST` | `0.0.0.0` | Bind host |
| `EMASS_MOCK_PORT` | `8080` | Bind port |
| `EMASS_MOCK_API_KEY` | `test-api-key` | Expected `api-key` header |
| `EMASS_MOCK_REQUIRE_API_KEY` | `true` | `false` disables auth |
| `EMASS_MOCK_SEED_SYSTEM_IDS` | `1,2,3` | Seed systems on startup |
| `PRISM_URL` | *(unset)* | Prism base URL for fallthrough. `docker-compose.yml` sets this. |

## mTLS

Real eMASS requires a DoD-issued client certificate. This harness does **not** enforce mTLS at the application layer — if you need to exercise cert-handling code, terminate TLS with a reverse proxy (nginx, Caddy, stunnel) in front of the harness and let it validate client certs. The harness does, however, enforce the EMU-style header pattern: both `api-key` and `user-uid` must be present on intercepted endpoints.

## Relation to MITRE's work

MITRE publishes:
- The [eMASS OpenAPI spec](https://github.com/mitre/emass_client/blob/main/docs/eMASSRestOpenApi.yaml) (Apache 2.0)
- Ruby / Python / TypeScript clients generated from that spec
- A public Stoplight mock at `https://stoplight.io/mocks/mitre/emasser/32836028`

This project:
- Vendors their spec in [`vendor/emass_client/`](vendor/emass_client/) (license + provenance noted)
- Runs Prism locally so you don't need to rely on the public mock's availability or rate limits
- Adds the stateful + failure-injection + test-harness layer on top

## Contributing

Issues and PRs welcome. Useful directions:

- New stateful handlers (milestones, device scan results, etc.) — be explicit about what assertions they unlock that Prism can't
- Additional failure modes (rate limiting, eventual consistency windows, malformed responses)
- Harness kits for other languages (Go, Node, Ruby — mirror the `examples/python-pytest/` shape)
- Scenario fixtures (pre-built system states for common test setups)

Before sending a PR:

```bash
ruff check src tests
pytest -q
```

## License

Apache 2.0 — see [LICENSE](LICENSE). Vendored MITRE material retains its Apache 2.0 license and copyright; see [`vendor/emass_client/`](vendor/emass_client/).
