"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

# A small, synthetic assessment-procedure table so test-result pushes work out
# of the box. The AP ids follow eMASS's ``<control>.<n>`` shape and the CCI
# numbers are real DISA CCI ids for those controls, but the pairing is ours:
# DISA's AP table is not public and this is NOT it. Seed the real one for a
# system through ``POST /_admin/systems/{id}/assessment-procedures`` or
# ``EMASS_MOCK_SEED_ASSESSMENT_PROCEDURES``.
DEFAULT_ASSESSMENT_PROCEDURES: tuple[tuple[str, str], ...] = (
    ("AC-1.1", "000001"),
    ("AC-1.2", "000002"),
    ("AC-2.1", "000015"),
    ("AC-2.2", "000016"),
    ("AC-3.1", "000213"),
    ("AU-2.1", "000123"),
    ("CM-6.1", "000366"),
    ("IA-2.1", "000764"),
    ("SC-7.1", "001097"),
    ("SI-2.1", "001225"),
)


@dataclass(frozen=True)
class Settings:
    api_key: str
    """Expected `api-key` header value. Set EMASS_MOCK_API_KEY to override."""

    require_api_key: bool
    """If False, skip api-key and user-uid header validation entirely."""

    require_user_uid_on_all: bool
    """If True, also require `user-uid` on GET requests. The spec and the live
    API only need it on PUT, POST, and DELETE, so this defaults to False."""

    seed_system_ids: tuple[int, ...]
    """System IDs pre-seeded in the state store on startup."""

    seed_assessment_procedures: tuple[tuple[str, str], ...]
    """(assessmentProcedure, cci) pairs seeded on every system."""

    prism_url: str | None
    """URL of a running Stoplight Prism mock serving the eMASS OpenAPI spec.
    Used to fall through to spec-conformant responses for endpoints we don't
    handle statefully. If unset, unhandled paths return 501."""


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() != "false"


def _parse_assessment_procedures(raw: str | None) -> tuple[tuple[str, str], ...]:
    if raw is None:
        return DEFAULT_ASSESSMENT_PROCEDURES
    pairs: list[tuple[str, str]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(
                "EMASS_MOCK_SEED_ASSESSMENT_PROCEDURES entries look like AC-1.1=000001"
            )
        ap, cci = chunk.split("=", 1)
        pairs.append((ap.strip(), cci.strip()))
    return tuple(pairs)


def load_settings() -> Settings:
    raw_ids = os.getenv("EMASS_MOCK_SEED_SYSTEM_IDS", "1,2,3")
    seed_ids = tuple(int(x.strip()) for x in raw_ids.split(",") if x.strip())
    return Settings(
        api_key=os.getenv("EMASS_MOCK_API_KEY", "test-api-key"),
        require_api_key=_flag("EMASS_MOCK_REQUIRE_API_KEY", "true"),
        require_user_uid_on_all=_flag("EMASS_MOCK_REQUIRE_USER_UID_ON_ALL", "false"),
        seed_system_ids=seed_ids,
        seed_assessment_procedures=_parse_assessment_procedures(
            os.getenv("EMASS_MOCK_SEED_ASSESSMENT_PROCEDURES")
        ),
        prism_url=os.getenv("PRISM_URL") or None,
    )
