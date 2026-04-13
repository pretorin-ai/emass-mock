# emass-mock

An open-source mock of the [eMASS](https://www.dcsa.mil/is/emass/) REST API. Drop-in replacement for local development, CI pipelines, and partner integration testing when you can't (or shouldn't) hit a real eMASS instance.

> **Not affiliated with the U.S. Department of Defense, DISA, or MITRE.** This project is independent and exists purely to make integration development with eMASS less painful. Do not point this at production data.

## What it does

- Serves the eMASS REST endpoints most integrators need: `GET /api/systems`, `PUT /api/systems/{id}/controls`, `POST /api/systems/{id}/test-results`, `POST /api/systems/{id}/artifacts`, `POST /api/systems/{id}/poams`.
- Matches the real API's envelope shape: `{"meta": {"code": 200}, "data": [...]}`.
- Stores everything pushed to it in-memory for inspection.
- Exposes **failure injection** controls so you can test retry logic, partial-failure handling, timeouts, and 5xx behavior.
- Ships with a small **inspector UI** at `/ui/` so you can see what's been pushed without `curl | jq`.

## Quick start

```bash
# Python
pip install -e ".[dev]"
emass-mock  # starts on http://localhost:8080

# Docker
docker compose up
```

Then:

```bash
curl -H "api-key: test-api-key" http://localhost:8080/api/systems
# -> {"meta":{"code":200},"data":[{"systemId":1,...},...]}
```

Open http://localhost:8080/ui/ for the inspector, or http://localhost:8080/docs for the OpenAPI reference.

## Configuration

All via environment variables:

| Var | Default | Purpose |
|-----|---------|---------|
| `EMASS_MOCK_HOST` | `0.0.0.0` | Bind host |
| `EMASS_MOCK_PORT` | `8080` | Bind port |
| `EMASS_MOCK_API_KEY` | `test-api-key` | Expected `api-key` header value |
| `EMASS_MOCK_REQUIRE_API_KEY` | `true` | Set to `false` to disable auth for quick exploration |
| `EMASS_MOCK_SEED_SYSTEM_IDS` | `1,2,3` | Comma-separated system IDs to seed on startup |

## Failure injection

Real eMASS integrations break in specific, frustrating ways — 5xx during large batches, per-control validation errors, timeouts. The mock lets you reproduce those on demand.

```bash
# Force every endpoint to return 503
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" \
     -d '{"global_status": 503}'

# Fail one specific control but accept the rest
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" \
     -d '{"control_status": {"SC-7": 422}}'

# Add 2 seconds of latency to every request
curl -X POST http://localhost:8080/_admin/failures \
     -H "content-type: application/json" \
     -d '{"latency_seconds": 2.0}'

# Clear all injected failures
curl -X DELETE http://localhost:8080/_admin/failures

# Reset everything (state + failure config)
curl -X POST http://localhost:8080/_admin/reset
```

Or use the inspector UI at `/ui/` — it has a form for all of the above.

## mTLS

Real eMASS requires a DoD-issued client certificate. For local testing against this mock, mTLS is **not enforced at the application layer** — if you need to test mTLS-specific code paths, terminate TLS with a reverse proxy (nginx, Caddy, stunnel) in front of the mock and let it validate client certs. Application-level cert validation would force every consumer of this mock to manage a CA, which defeats the purpose of a frictionless dev tool.

## Endpoint reference

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/systems` | List systems (paginated). Auth probe. |
| `GET` | `/api/systems/{id}` | System detail. |
| `GET` | `/api/systems/{id}/controls` | List stored controls. |
| `PUT` | `/api/systems/{id}/controls` | Push control updates. Returns `{accepted, rejected}`. |
| `GET` | `/api/systems/{id}/test-results` | List stored test results. |
| `POST` | `/api/systems/{id}/test-results` | Submit test results. |
| `GET` | `/api/systems/{id}/artifacts` | List stored artifacts. |
| `POST` | `/api/systems/{id}/artifacts` | Upload artifacts (JSON descriptor). |
| `GET` | `/api/systems/{id}/poams` | List stored POA&Ms. |
| `POST` | `/api/systems/{id}/poams` | Create POA&Ms. |

Admin (not part of the real eMASS surface):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/_admin/reset` | Clear state, reseed systems, clear failures. |
| `GET` | `/_admin/state` | Dump store + failure config as JSON. |
| `POST` | `/_admin/failures` | Configure failure injection. |
| `DELETE` | `/_admin/failures` | Clear injected failures. |
| `GET` | `/health` | Liveness probe. |
| `GET` | `/ui/` | Inspector UI. |
| `GET` | `/docs` | OpenAPI/Swagger docs. |

## Contributing

Issues and PRs welcome — especially:

- New eMASS endpoints we haven't covered yet
- More realistic response fixtures (we'd love contributions from people with real eMASS access who can share sanitized shapes)
- Additional failure modes

Before sending a PR:

```bash
ruff check src tests
pytest -q
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
