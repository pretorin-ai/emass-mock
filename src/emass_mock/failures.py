"""Failure-injection registry.

Lets tests force the mock into specific failure modes:
- global status override (every request returns N)
- per-path status override
- per-control failure (control acronym → status code)
- artificial latency (seconds)

Configured via the admin API (see routers/admin.py).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class FailureConfig:
    global_status: int | None = None
    path_status: dict[str, int] = field(default_factory=dict)
    control_status: dict[str, int] = field(default_factory=dict)
    latency_seconds: float = 0.0

    def reset(self) -> None:
        self.global_status = None
        self.path_status.clear()
        self.control_status.clear()
        self.latency_seconds = 0.0


_failures = FailureConfig()


def get_failures() -> FailureConfig:
    return _failures


async def maybe_sleep() -> None:
    if _failures.latency_seconds > 0:
        await asyncio.sleep(_failures.latency_seconds)
