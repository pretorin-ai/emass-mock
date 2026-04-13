"""In-memory state store powering deterministic round-trips.

This is the core of what this harness adds on top of Stoplight Prism. Every
write handler mirrors payloads into the store; every read handler serves from
it. Without this, tests cannot assert "I wrote X, GET returned X."

Not persistent across restarts. Reset via the admin API between test runs.
Single-process, single-worker assumptions — fine for a test harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SystemRecord:
    system_id: int
    name: str = "Mock System"
    acronym: str = "MOCK"
    controls: dict[str, dict[str, Any]] = field(default_factory=dict)
    test_results: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    poams: list[dict[str, Any]] = field(default_factory=list)
    _poam_counter: int = 0

    def next_poam_id(self) -> int:
        self._poam_counter += 1
        # Real eMASS poamIds are large; start at 1000 for readability.
        return 1000 + self._poam_counter


class Store:
    def __init__(self) -> None:
        self.systems: dict[int, SystemRecord] = {}

    def seed(self, system_ids: tuple[int, ...]) -> None:
        for sid in system_ids:
            if sid not in self.systems:
                self.systems[sid] = SystemRecord(system_id=sid, acronym=f"MOCK-{sid}")

    def reset(self, system_ids: tuple[int, ...]) -> None:
        self.systems.clear()
        self.seed(system_ids)

    def get_system(self, system_id: int) -> SystemRecord | None:
        return self.systems.get(system_id)

    def list_systems(self) -> list[SystemRecord]:
        return list(self.systems.values())


_store = Store()


def get_store() -> Store:
    return _store
