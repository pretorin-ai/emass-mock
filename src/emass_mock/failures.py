"""Failure-injection registry.

Lets tests force the mock into specific failure modes:
- global status override (every request returns N)
- per-path status override
- per-control failure (control acronym → status code)
- per-artifact-filename-suffix status (reject only certain uploaded files — e.g.
  reject ``.cklb`` while accepting ``.ckl`` to exercise format fallbacks)
- force an empty artifact response (2xx with no per-row confirmation)
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
    # Reject an uploaded artifact when its filename ends with one of these
    # suffixes, with the given status. Lets tests reject one format (".cklb")
    # while accepting another (".ckl") on the shared /artifacts path, which
    # global/path status cannot distinguish.
    artifact_filename_status: dict[str, int] = field(default_factory=dict)
    # Return a 2xx artifact response with an empty data array (no per-row echo) —
    # models a non-compliant/proxied server so callers can prove they don't treat
    # an unconfirmed upload as a confirmed success.
    artifact_force_empty: bool = False
    latency_seconds: float = 0.0

    def reset(self) -> None:
        self.global_status = None
        self.path_status.clear()
        self.control_status.clear()
        self.artifact_filename_status.clear()
        self.artifact_force_empty = False
        self.latency_seconds = 0.0


_failures = FailureConfig()


def get_failures() -> FailureConfig:
    return _failures


async def maybe_sleep() -> None:
    if _failures.latency_seconds > 0:
        await asyncio.sleep(_failures.latency_seconds)
