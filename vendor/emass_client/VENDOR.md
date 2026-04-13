# Vendored: mitre/emass_client

This directory contains a pinned copy of files from [mitre/emass_client](https://github.com/mitre/emass_client), used as the source of truth for eMASS API behavior in this project.

## Source

- **Repository**: https://github.com/mitre/emass_client
- **Commit**: `c9013aafc5319fd7e2c74bba6e56cdf535959e70`
- **License**: Apache 2.0 (see `LICENSE.md` in this directory)
- **Copyright**: © The MITRE Corporation

## Files

| File | Purpose |
|------|---------|
| `eMASSRestOpenApi.yaml` | OpenAPI 3.0.3 spec. Loaded by Stoplight Prism to generate spec-conformant responses. |
| `LICENSE.md` | Apache 2.0 license as published by MITRE. |
| `NOTICE.md` | MITRE copyright notice. |

## Why vendored (not submoduled)

Simpler for users (no `git submodule update --init` step). Updates are a deliberate, reviewed action — drop a new copy of the spec, update the commit hash here, run the test suite against the new shapes.

## Updating

```bash
# From the root of this repo
curl -L https://raw.githubusercontent.com/mitre/emass_client/<new-sha>/docs/eMASSRestOpenApi.yaml \
    -o vendor/emass_client/eMASSRestOpenApi.yaml
# Update the commit SHA in this file.
# Run the test suite, fix any shape drift, commit.
```

## Not affiliated with MITRE or DoD

This project is independent. MITRE publishes the spec under Apache 2.0; we consume it to power a stateful test harness. No endorsement implied.
