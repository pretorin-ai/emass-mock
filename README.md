# emass-mock

**A spec-enforcing, stateful test harness for eMASS integrations.** Built on MITRE's official [eMASS OpenAPI spec](https://github.com/mitre/emass_client) (eMASS API v3.22) and [Stoplight Prism](https://github.com/stoplightio/prism). It validates every write against the spec, round-trips what you wrote, injects failures on demand, and ships a copy-paste pytest harness.

> **Not affiliated with the U.S. Department of Defense, DISA, or MITRE.** Independent project. Do not point this at production data.

## The pitch

If you're writing code that pushes to eMASS, you already know Stoplight Prism exists. It serves MITRE's OpenAPI spec as a mock and validates your outgoing payloads. That's great for unit-testing your serializer.

It is **not enough** to test a real integration, because:

- Prism is **stateless.** PUT a control, GET it back, you receive random fake data unrelated to what you pushed. You can't assert `assert control.status == "Planned"` after a write.
- Prism returns **one status per request.** Real eMASS returns mixed success/failure rows within a single batch response; your partial-failure handling code cannot be tested against it.
- Prism has no **idempotency semantics.** Retry logic is untestable.

This harness sits in front of Prism and intercepts the endpoints that need state. Those endpoints validate requests against the same spec, so a payload that drifts from the contract fails here before it fails in eMASS. Everything else proxies to Prism.

## Value pillars

| Pillar | What it unlocks | Prism alone? |
|--------|-----------------|--------------|
| **1. Deterministic round-tripping** | `assert what_i_wrote == what_i_read` on controls, POA&Ms, milestones, test results, artifacts, baselines. | No |
| **2. Orchestrated failure injection** | Per-control failures inside a batch. Global 5xx. Per-file artifact rejection. Latency. Recoverable between tests. | No |
| **3. Spec enforcement with state** | Request bodies validated against the vendored OpenAPI operation; responses shaped to the spec; a 400 names the operation and the fields. | Partly |
| **4. Pytest harness starter kit** | Drop-in fixtures + reference tests. Clone, adapt, done. | No |
| **(Inherited)** Spec-conformant example responses for dashboards, workflows, CMMC, etc. | Yes, via Prism proxy |

## Architecture

```
your code
    │
    │ (api-key on every call, user-uid on writes)
    ▼
┌───────────────────────────────────────────────┐
│  emass-mock  :8080                            │
│                                               │
│  ┌──────────────┐ ┌───────────────┐           │
│  │ State store  │ │ Failure inj.  │           │
│  └──────────────┘ └───────────────┘           │
│  ┌─────────────────────────────────────────┐  │
│  │ Spec validator (vendored OpenAPI v3.22) │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  Stateful handlers:                           │
│    GET  /api                                  │
│    GET  /api/systems*                         │
│    PUT/GET        .../controls                │
│    POST/GET       .../test-results            │
│    POST/GET       .../artifacts   (multipart) │
│    POST/PUT/DELETE/GET .../poams[/{id}]       │
│    GET/POST/PUT/DELETE .../poams/{id}/milestones[/{id}] │
│    GET/POST/PUT/DELETE .../hw-baseline        │
│    GET/POST/PUT/DELETE .../sw-baseline        │
│    POST           .../device-scan-results     │
│                                               │
│  Everything else  ──►  Prism                  │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  Stoplight Prism    │
            │  :4010 (internal)   │
            │  vendor/emass_client│
            │   /eMASSRestOpenApi │
            │   .yaml             │
            └─────────────────────┘
```

## Quick start

```bash
docker compose up -d
curl -H "api-key: test-api-key" http://localhost:8080/api
# → {"meta":{"code":200},"data":{"success":true}}

curl -H "api-key: test-api-key" http://localhost:8080/api/systems
# → {"meta":{"code":200},"data":[{"systemId":1,...},...]}

# Round-trip test (writes need user-uid)
curl -X PUT http://localhost:8080/api/systems/1/controls \
     -H "api-key: test-api-key" -H "user-uid: 1234567890" \
     -H "content-type: application/json" \
     -d '[{"acronym":"AC-2","responsibleEntities":"System Owner","controlDesignation":"System-Specific","estimatedCompletionDate":1799644800,"implementationNarrative":"AC-2 implementation narrative","implementationStatus":"Planned","slcmCriticality":"Moderate","slcmFrequency":"Quarterly","slcmMethod":"Manual","slcmReporting":"Tracked","slcmTracking":"Tracked","slcmComments":"Tracked"}]'

curl -H "api-key: test-api-key" http://localhost:8080/api/systems/1/controls
# → {"meta":{"code":200},"data":[{"acronym":"AC-2",...,"ccis":"000015,000016"}]}

# A payload the spec rejects is a 400 that names the operation and the field
curl -X PUT http://localhost:8080/api/systems/1/controls \
     -H "api-key: test-api-key" -H "user-uid: 1234567890" \
     -H "content-type: application/json" -d '[{"acronym":"AC-2"}]'
# → {"meta":{"code":400,"errorMessage":"Request body does not match updateControlBySystemId in eMASS API v3.22: 0: 'responsibleEntities' is a required property; ..."}}
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
    resp = emass.put("/api/systems/1/controls", json=[control("AC-2"), control("SC-7")])
    rows = {r["acronym"]: r for r in resp.json()["data"]}
    assert rows["AC-2"]["success"] is True
    assert rows["SC-7"]["success"] is False
    assert rows["SC-7"]["errors"] == ["acronym: injected failure (422) for SC-7"]
```

## What the spec validation does

Every write handler names the spec operation it implements (`updateControlBySystemId`, `addTestResultsBySystemId`, ...) and validates the body with a JSON Schema compiled from that operation's `requestBody`. Two kinds of failure, matching how eMASS reports them:

- **Schema violation** (missing required field, wrong type, bad enum, unknown field): HTTP 400 for the whole batch, in the eMASS envelope, listing the operation and up to 25 problems.
- **Business rule** the schema cannot express (a control's `[Conditional]` SLCM fields, an unknown `assessmentProcedure`, an unknown `poamId` on PUT): HTTP 200 with that row's `success: false` and an `errors` array of `"key: value"` strings.

Unknown fields are rejected by default. `EMASS_MOCK_UNKNOWN_FIELDS=allow` keeps type, enum and required checks but lets extra fields through.

The spec is OpenAPI 3.0, so `src/emass_mock/spec.py` bridges it to JSON Schema: `nullable`, `allOf` property bags, and the spec's habit of putting `required` on the array instead of the rows. Read the module docstring before changing it.

Responses are shaped to the spec's declared response schemas, and the test suite validates them the same way (`conforms` fixture), so the mock's own answers are kept honest.

## Test results and assessment procedures

eMASS keys a test result by **assessment procedure** (`AC-1.1`), not by CCI, and reports the CCI back. The mock holds a per-system procedure table:

- A small synthetic default is seeded on every system (see `config.py`; the pairing is ours, not DISA's).
- Override at startup with `EMASS_MOCK_SEED_ASSESSMENT_PROCEDURES="AC-1.1=000001,SC-7.1=001097"`.
- Extend at runtime with `POST /_admin/systems/{id}/assessment-procedures` and a `{"AC-1.1": "000001"}` body.

A POST for a procedure the system does not know fails that row. `GET /controls` exposes the CCIs per control (`ccis`) and `GET /test-results` returns both ids per row, which is how a client can learn the mapping from eMASS itself.

## Failure injection reference

Admin API (not part of the real eMASS surface):

```bash
# Global 5xx on every request
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" -d '{"global_status": 503}'

# Fail one control in a batch (the other controls still succeed)
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" -d '{"control_status": {"SC-7": 422}}'

# Reject one artifact format while accepting another (e.g. .cklb vs .ckl)
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" -d '{"artifact_filename_status": {".cklb": 422}}'

# 2xx artifact response with no per-row confirmation (a misbehaving proxy)
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" -d '{"artifact_force_empty": true}'

# Add latency
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" -d '{"latency_seconds": 2.0}'

# Scope a status to one path (409 is how eMASS says a batch was too large)
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" -d '{"path_status": {"/api/systems/1/controls": 409}}'

# Reset everything (state, failures, procedure tables)
curl -X POST http://localhost:8080/_admin/reset
```

Other admin routes: `GET /_admin/state`, `GET/POST /_admin/systems/{id}/assessment-procedures`, `GET /_admin/systems/{id}/artifacts` (uploaded bytes as `_content_b64`, plus `_part_name`), `GET /_admin/systems/{id}/device-scans`.

## What's stateful, what proxies to Prism

**Stateful handlers** (validated against the spec, persisted, replayed):

- `GET /api` (connectivity probe)
- `GET /api/systems`, `GET /api/systems/{id}` (seeded deterministically; spec filters ignored)
- `PUT /api/systems/{id}/controls` + `GET` (with `acronyms` filter and read-only `ccis`)
- `POST /api/systems/{id}/test-results` + `GET` (`controlAcronyms`, `assessmentProcedures`, `ccis`, `latestOnly`)
- `POST /api/systems/{id}/artifacts` (multipart, `isBulk`) + `GET` (`filename`)
- `POST`, `PUT`, `DELETE`, `GET /api/systems/{id}/poams`, `GET .../poams/{poamId}` (`systemOnly` defaults to true per the spec)
- `GET`, `POST`, `PUT`, `DELETE .../poams/{poamId}/milestones`, `GET .../milestones/{milestoneId}`
- `GET`, `POST`, `PUT`, `DELETE /api/systems/{id}/hw-baseline` and `/sw-baseline` (GET paginated)
- `POST /api/systems/{id}/device-scan-results` (multipart, `scanType` enum)

**Everything else** (dashboards, workflows, CMMC, CAC/PAC, artifact export, cloud/container/static scans, ...) falls through to Prism, which returns spec-conformant example data. If you hit the harness without `PRISM_URL` set, unhandled paths return `501` with an explanatory message.

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `EMASS_MOCK_HOST` | `0.0.0.0` | Bind host |
| `EMASS_MOCK_PORT` | `8080` | Bind port |
| `EMASS_MOCK_API_KEY` | `test-api-key` | Expected `api-key` header |
| `EMASS_MOCK_REQUIRE_API_KEY` | `true` | `false` disables header auth entirely |
| `EMASS_MOCK_REQUIRE_USER_UID_ON_ALL` | `false` | `true` also requires `user-uid` on GET (the spec and the live API only need it on writes) |
| `EMASS_MOCK_UNKNOWN_FIELDS` | `reject` | `allow` lets undeclared request fields through |
| `EMASS_MOCK_SEED_SYSTEM_IDS` | `1,2,3` | Seed systems on startup |
| `EMASS_MOCK_SEED_ASSESSMENT_PROCEDURES` | built-in synthetic set | `AP=CCI,...` pairs seeded on every system |
| `EMASS_MOCK_SPEC_PATH` | packaged copy | Path to an alternative `eMASSRestOpenApi.yaml` |
| `PRISM_URL` | *(unset)* | Prism base URL for fallthrough. `docker-compose.yml` sets this. |

## Auth and mTLS

Real eMASS requires a DoD-issued client certificate on every call, `api-key` on every call, and `user-uid` on PUT, POST and DELETE. This harness enforces the two headers that way. It does **not** terminate TLS: if you need to exercise cert-handling code, put a reverse proxy (nginx, Caddy, stunnel) in front of it and let that validate client certs.

[`deathlabs/emu`](https://github.com/deathlabs/emu) is the reference for how a working client behaves against the live DoD instance. Where its observed behaviour and the v3.22 spec disagree (the multipart part name, for one), [`docs/live-api-observations.md`](docs/live-api-observations.md) records both and says what the mock does.

## Relation to MITRE's work

MITRE publishes:
- The [eMASS OpenAPI spec](https://github.com/mitre/emass_client/blob/main/docs/eMASSRestOpenApi.yaml) (Apache 2.0)
- Ruby / Python / TypeScript clients generated from that spec
- A public Stoplight mock at `https://stoplight.io/mocks/mitre/emasser/32836028`

This project:
- Vendors their spec in [`vendor/emass_client/`](vendor/emass_client/) (license + provenance noted) and packages a byte-identical copy in `src/emass_mock/spec/` so an installed wheel can validate without the repo checkout; a test keeps the two in sync
- Runs Prism locally so you don't need to rely on the public mock's availability or rate limits
- Adds the validation + stateful + failure-injection + test-harness layer on top

## Contributing

Issues and PRs welcome. Useful directions:

- Handlers for the endpoints the live API has beyond v3.22 (see the observations doc), labelled as unspecified
- Additional failure modes (rate limiting, 409 batch splitting, eventual consistency windows, malformed responses)
- Harness kits for other languages (Go, Node, Ruby; mirror the `examples/python-pytest/` shape)
- Scenario fixtures (pre-built system states for common test setups)

Before sending a PR:

```bash
ruff check src tests
ruff format --check src tests
pytest -q
```

## License

Apache 2.0, see [LICENSE](LICENSE). Vendored MITRE material retains its Apache 2.0 license and copyright; see [`vendor/emass_client/`](vendor/emass_client/).
