"""In-memory store for systems, controls, test results, artifacts, POA&Ms.

Not persistent. Reset via the admin API. Thread-safety is not a concern for
typical mock-server use (single uvicorn worker, test scenarios are sequential).
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


class Store:
    def __init__(self) -> None:
        self.systems: dict[int, SystemRecord] = {}

    def seed(self, system_ids: tuple[int, ...]) -> None:
        for sid in system_ids:
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
