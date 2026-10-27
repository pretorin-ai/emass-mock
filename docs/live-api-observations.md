# Live eMASS API observations vs the vendored spec

The mock validates against MITRE's published OpenAPI document
(`vendor/emass_client/eMASSRestOpenApi.yaml`, eMASS API **v3.22**, February
2025). That is the only public spec. The live DoD instance is newer: the
eMASS Updater CLI ([deathlabs/emu](https://github.com/deathlabs/emu)), which
runs against `connect.emass.apps.mil` with an NPE certificate, pins its
reference to the eMASS API guide **v3.32.0** (its 4.0.5 release, August
2026). The v3.3x guide is distributed by DISA and is not public.

This file records where the live API is known or suspected to differ from
v3.22, with the evidence. The mock follows the spec unless a row below says
otherwise. Confirm anything marked *unverified* against a real instance
before relying on it.

## Authentication

| Topic | Spec v3.22 | Observed (emu) | Mock |
|---|---|---|---|
| `api-key` header | every call | every call | required on every intercepted call |
| `user-uid` header | "needed for PUT, POST, DELETE" | removed from GET in emu 4.0.3; writes still send it | required on writes; `EMASS_MOCK_REQUIRE_USER_UID_ON_ALL=true` extends to GET |
| Client certificate | DoD PKI, every call | `tls.LoadX509KeyPair`, TLS 1.2 minimum, system trust store | not enforced; terminate TLS in front of the mock |
| `api-version` header or query | optional; unset means latest | not sent | ignored |

## Status codes

emu maps **HTTP 409** to "too much data was requested in a single batch" and
calls it eMASS-specific. The spec does not list 409 on any operation. The
mock does not emit it yet; failure injection can produce it
(`{"path_status": {"/api/systems/1/controls": 409}}`).

The spec lists **490 "API Rule Failed"** on most GETs. Neither emu nor the
mock handle it specially.

## Multipart uploads (artifacts, device scan results)

| Topic | Spec v3.22 | Observed (emu) | Mock |
|---|---|---|---|
| Binary part name | `filename` | `file` | accepts both; records which one arrived as `_part_name` in the admin view |
| Artifact text fields | `isTemplate`, `type`, `category` | emu sends only the file | optional, spec defaults applied (`false`, `Other`, `Evidence`) |
| Bulk upload | `isBulk=true` query, single `.zip` | same | enforced |
| Scan upload path | `/api/systems/{id}/device-scan-results` | same | same; the old `/scan-results` path falls through |
| `scanType` | enum of 6 | same 7 in emu (adds `acasConsolidatedArf`) | spec enum enforced |

emu's artifact and device-scan uploads are marked validated against the live
instance in its TODO list, so the `file` part name is the stronger evidence.
*Unverified*: whether the live API also accepts `filename`.

## Test results

The v3.22 request body is `testedBy, testDate, description, complianceStatus,
assessmentProcedure` with `additionalProperties: false`. There is no `cci`
in the request; the CCI comes back in the response row. Assessment
procedure ids look like `AC-1.1`. A client that sends a CCI number, a NIST
control id, or a STIG rule id as the procedure is not speaking eMASS.

The GET response carries both `cci` and `assessmentProcedure` per row, and
`GET /controls` carries the comma-separated `ccis` per control, so a client
can learn the system's CCI to procedure mapping from eMASS itself.

*Unverified*: whether the live API silently drops an unknown `cci` field or
rejects the row. The mock rejects it (400) by default;
`EMASS_MOCK_UNKNOWN_FIELDS=allow` relaxes that.

## POA&Ms and milestones

* `GET /poams` has `systemOnly` **defaulting to true** in the spec, which
  excludes control-level and assessment-procedure-level items. A client that
  reads back POA&Ms it created against a control must pass `systemOnly=false`.
  The mock follows the spec.
* `PUT /poams` requires `poamId` **and** `displayPoamId`.
* emu's POA&M model sends milestone fields (`status`, `statusComments`,
  `completionDate`, `isActive`) that the v3.22 nested-milestone schema does
  not declare. emu has not validated its POA&M upload against the live API
  (its TODO), so this is *unverified* either way. The mock rejects them.
* Nested milestones on `PUT /poams` carry no `milestoneId` in the spec. The
  mock matches them to existing milestones by description.

## Baselines

* `POST` / `PUT` responses are `{systemId, hardwareId|softwareId, success,
  errors}` only. They do not echo `assetName` or `softwareName`; pair rows
  with the request by position.
* `GET` is paginated (`pageIndex`, `pageSize` default 20000) and returns a
  `pagination` block.

## Endpoints the live API has and v3.22 does not

emu calls these against the live instance; none appear in the v3.22 spec:

| Path | emu command | Notes |
|---|---|---|
| `GET /api/systems/{id}/applications` | `get applications` | paginated |
| `GET /api/systems/{id}/containers` | `get containers` | paginated |
| `POST /api/systems/{id}/containers/sbom` | `upload container-sbom` | multipart `file` + `containerName`, `containerIdentifier`, `format` |
| `GET /api/systems/{id}/devices` | `get devices` | paginated; rows have `deviceId`, `fqdn`, `hostname`, `lastScanDate`, `nickname` |
| `GET /api/systems/{id}/cloud-resources` | `get cloud-resources` | paginated |
| `GET /api/systems/{id}/ports-protocols` | `get pps` | emu reports a 403 here, unresolved |
| `GET /api/systems/{id}/device-scan-results` | `get device-scan-results` | v3.22 only has POST |
| `GET /api/systems/{id}/static-code-scans` | `get static-code-scans` | v3.22 only has POST |
| `GET /api/systems/{id}/container-scan-results` | `get container-scan-results` | v3.22 only has POST |

The mock does not implement these. They fall through to Prism, which does
not know them either, so they return whatever Prism does for an unknown
path. Adding them means writing handlers from emu's observed shapes, clearly
labelled as unspecified.

## Updating this file

When a real instance confirms or refutes a row, replace *unverified* with
the date and the instance (sandbox or production), and adjust the mock in
the same change.
