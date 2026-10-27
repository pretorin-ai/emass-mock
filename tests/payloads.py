"""Spec-shaped request rows shared by the tests."""

from __future__ import annotations

from typing import Any


def control_row(acronym: str, **overrides: Any) -> dict[str, Any]:
    """A ``ControlsRequestPutBody`` row that satisfies the Planned conditional rules."""
    row = {
        "acronym": acronym,
        "responsibleEntities": "System Owner",
        "controlDesignation": "System-Specific",
        "estimatedCompletionDate": 1799644800,
        "implementationNarrative": f"{acronym} implementation narrative",
        "implementationStatus": "Planned",
        "slcmCriticality": "Moderate",
        "slcmFrequency": "Quarterly",
        "slcmMethod": "Manual",
        "slcmReporting": "Tracked in Pretorin",
        "slcmTracking": "Tracked in Pretorin",
        "slcmComments": "Tracked in Pretorin",
    }
    row.update(overrides)
    return row


def result_row(procedure: str = "AC-1.1", **overrides: Any) -> dict[str, Any]:
    """A ``TestResultsRequestPostBody`` row."""
    row = {
        "testedBy": "Smith, Joe",
        "testDate": 1799644800,
        "description": "Test result description",
        "complianceStatus": "Compliant",
        "assessmentProcedure": procedure,
    }
    row.update(overrides)
    return row


def poam_row(**overrides: Any) -> dict[str, Any]:
    """A ``PoamRequestPostBody`` row with the spec's five required fields."""
    row = {
        "status": "Ongoing",
        "vulnerabilityDescription": "SC-7 boundary protection gap",
        "sourceIdentifyingVulnerability": "Pretorin assessment",
        "pocOrganization": "Cyberdyne Systems",
        "resources": "2 FTE",
    }
    row.update(overrides)
    return row
