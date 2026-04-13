"""CLI entrypoint: `python -m emass_mock` or `emass-mock`."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("EMASS_MOCK_HOST", "0.0.0.0")
    port = int(os.getenv("EMASS_MOCK_PORT", "8080"))
    uvicorn.run("emass_mock.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
