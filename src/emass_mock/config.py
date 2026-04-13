"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_key: str
    """Expected `api-key` header value. Set EMASS_MOCK_API_KEY to override."""

    require_api_key: bool
    """If False, skip api-key header validation. Useful for quick local testing."""

    seed_system_ids: tuple[int, ...]
    """System IDs that exist by default in the mock. Comma-separated env var."""


def load_settings() -> Settings:
    api_key = os.getenv("EMASS_MOCK_API_KEY", "test-api-key")
    require_api_key = os.getenv("EMASS_MOCK_REQUIRE_API_KEY", "true").lower() != "false"
    raw_ids = os.getenv("EMASS_MOCK_SEED_SYSTEM_IDS", "1,2,3")
    seed_ids = tuple(int(x.strip()) for x in raw_ids.split(",") if x.strip())
    return Settings(
        api_key=api_key,
        require_api_key=require_api_key,
        seed_system_ids=seed_ids,
    )
