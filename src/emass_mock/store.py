"""In-memory state store powering deterministic round-trips.

This is the core of what this harness adds on top of Stoplight Prism. Every
write handler mirrors payloads into the store; every read handler serves from
it. Without this, tests cannot assert "I wrote X, GET returned X."

Not persistent across restarts. Reset via the admin API between test runs.
Single-process, single-worker assumptions; fine for a test harness.
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
    hardware: dict[str, dict[str, Any]] = field(default_factory=dict)
    software: dict[str, dict[str, Any]] = field(default_factory=dict)
    device_scans: list[dict[str, Any]] = field(default_factory=list)
    # assessmentProcedure -> CCI. eMASS keys test results by assessment
    # procedure and reports the CCI back; a POST for an unknown procedure
    # fails per row. Seeded from settings, extended through the admin API.
    assessment_procedures: dict[str, str] = field(default_factory=dict)
    _poam_counter: int = 0
    _milestone_counter: int = 0
    _hw_counter: int = 0
    _sw_counter: int = 0

    def next_poam_id(self) -> int:
        self._poam_counter += 1
        # Real eMASS poamIds are large; start at 1000 for readability.
        return 1000 + self._poam_counter

    def display_poam_id(self, poam_id: int) -> int:
        # eMASS shows a separate human-facing id (``displayPoamId``).
        return 100_000_000 + poam_id

    def next_milestone_id(self) -> int:
        self._milestone_counter += 1
        return 5000 + self._milestone_counter

    def next_hardware_id(self) -> str:
        self._hw_counter += 1
        # Real eMASS hardwareIds are GUIDs; this mock uses a deterministic
        # sequence so tests can assert exact values.
        return f"00000000-0000-4000-8000-{self._hw_counter:012d}"

    def next_software_id(self) -> str:
        self._sw_counter += 1
        return f"11111111-1111-4111-8111-{self._sw_counter:012d}"

    def find_poam(self, poam_id: int) -> dict[str, Any] | None:
        return next((p for p in self.poams if p.get("poamId") == poam_id), None)

    def ccis_for_control(self, acronym: str) -> list[str]:
        prefix = f"{acronym.upper()}."
        return sorted(
            cci for ap, cci in self.assessment_procedures.items() if ap.upper().startswith(prefix)
        )


class Store:
    def __init__(self) -> None:
        self.systems: dict[int, SystemRecord] = {}
        self._seed_assessment_procedures: tuple[tuple[str, str], ...] = ()

    def seed(
        self,
        system_ids: tuple[int, ...],
        assessment_procedures: tuple[tuple[str, str], ...] | None = None,
    ) -> None:
        if assessment_procedures is not None:
            self._seed_assessment_procedures = assessment_procedures
        for sid in system_ids:
            if sid not in self.systems:
                self.systems[sid] = SystemRecord(
                    system_id=sid,
                    acronym=f"MOCK-{sid}",
                    assessment_procedures=dict(self._seed_assessment_procedures),
                )

    def reset(
        self,
        system_ids: tuple[int, ...],
        assessment_procedures: tuple[tuple[str, str], ...] | None = None,
    ) -> None:
        self.systems.clear()
        self.seed(system_ids, assessment_procedures)

    def get_system(self, system_id: int) -> SystemRecord | None:
        return self.systems.get(system_id)

    def list_systems(self) -> list[SystemRecord]:
        return list(self.systems.values())


_store = Store()


def get_store() -> Store:
    return _store
