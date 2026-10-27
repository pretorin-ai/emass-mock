# Changelog

## 0.2.0 (2026-10-27)

The mock now enforces the eMASS contract instead of restating the client it
was first written for.

### Changed

- Every write handler validates its request body against the operation's
  schema in the vendored MITRE OpenAPI document (eMASS API v3.22). A body the
  spec would reject is a 400 in the eMASS envelope naming the operation and
  the offending fields. Unknown fields are rejected by default;
  `EMASS_MOCK_UNKNOWN_FIELDS=allow` relaxes that.
- Test results: `cci` is no longer accepted in the request (the spec never
  declared it). Rows are keyed by `assessmentProcedure`, the CCI is resolved
  from a per-system procedure table and reported back as the spec's
  `TestResultsPost` row. The invented `testResultId` is gone. GET honours
  `controlAcronyms`, `assessmentProcedures`, `ccis` and `latestOnly`.
- `user-uid` is required on PUT, POST and DELETE only.
  `EMASS_MOCK_REQUIRE_USER_UID_ON_ALL` now defaults to `false`.
- Auth failures, malformed JSON and FastAPI's own errors are rendered in the
  eMASS error envelope, never as `{"detail": ...}`.
- Per-row `errors` are arrays of `"key: value"` strings (the spec's `Errors`
  type), not objects.
- Artifacts POST is multipart only. The JSON-descriptor mode is gone. The
  binary part may be named `filename` (spec) or `file` (observed in emu);
  the name used is recorded. Public GET rows are spec-shaped; uploaded bytes
  moved to `GET /_admin/systems/{id}/artifacts`.
- Hardware and software baseline responses are the spec's
  `{systemId, <id>, success, errors}` rows; GET is paginated and carries the
  `pagination` block.
- Controls GET adds the read-only `ccis` field and filters by `acronyms`.
- Controls conditional rules fail per row instead of failing the batch.

### Added

- **Testing UI** under `/ui/`, self-contained (no CDN):
  - *Console*: send any spec operation with parameters, headers, and a body
    generated from the spec's examples; validate without sending; multipart
    uploads with a choice of part name; per-row result summary; copy as curl.
  - *Traffic*: live log of every `/api` request with the matched spec
    operation, handler (mock, Prism, unhandled, injected), auth status,
    request body or multipart parts, spec problems, and response.
  - *System* pages for every stored resource, artifact downloads, and
    assessment-procedure editing; a *Failures* page for every rule type.
- Request log middleware (`traffic.py`) and `x-emass-mock-request-id` on
  every `/api` response; `EMASS_MOCK_TRAFFIC_LIMIT` (default 500).
- Admin JSON for the UI: `/_admin/operations`, `/operations/{id}/example`,
  `/validate`, `/requests`, `/settings`, `/failures` (GET), artifact content.
- Example bodies generated from the spec, coerced to each field's declared
  type (several MITRE examples are unquoted YAML numbers on string fields).
- `GET /api` (`testConnection`).
- `PUT` and `DELETE /api/systems/{id}/poams`, `GET /poams/{poamId}`.
- Milestones: `GET`, `POST`, `PUT`, `DELETE /poams/{poamId}/milestones` and
  `GET /milestones/{milestoneId}`.
- `POST /api/systems/{id}/device-scan-results` (multipart, `scanType` enum
  checked against the spec).
- Admin: assessment-procedure seeding, raw artifact and device-scan views,
  richer `/_admin/state`.
- `docs/live-api-observations.md`: where the live API is known or suspected
  to differ from v3.22, with evidence from `deathlabs/emu`.
- The spec is packaged (`src/emass_mock/spec/`) so an installed wheel
  carries it; a test keeps it byte-identical to `vendor/`.

### Dependencies

- `pyyaml`, `jsonschema`.

## 0.1.0

Initial release: stateful systems, controls, test results, artifacts and
POA&M handlers in front of Stoplight Prism, failure injection, pytest kit.
