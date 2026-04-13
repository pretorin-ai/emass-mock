"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_key: str
    """Expected `api-key` header value. Set EMASS_MOCK_API_KEY to override."""

    require_api_key: bool
    """If False, skip api-key header validation."""

    seed_system_ids: tuple[int, ...]
    """System IDs pre-seeded in the state store on startup."""

    prism_url: str | None
    """URL of a running Stoplight Prism mock serving the eMASS OpenAPI spec.
    Used to fall through to spec-conformant responses for endpoints we don't
    handle statefully. If unset, unhandled paths return 501."""


def load_settings() -> Settings:
    raw_ids = os.getenv("EMASS_MOCK_SEED_SYSTEM_IDS", "1,2,3")
    seed_ids = tuple(int(x.strip()) for x in raw_ids.split(",") if x.strip())
    return Settings(
        api_key=os.getenv("EMASS_MOCK_API_KEY", "test-api-key"),
        require_api_key=os.getenv("EMASS_MOCK_REQUIRE_API_KEY", "true").lower() != "false",
        seed_system_ids=seed_ids,
        prism_url=os.getenv("PRISM_URL") or None,
    )
