"""Request bodies are validated against the vendored spec, not hand-written rules.

The drift this guards against is real: an earlier version of this mock
*required* ``cci`` on test-results POST, a field the spec never declares, and
the client it was written for sent it. Every stateful write endpoint now goes
through ``spec.validate_request`` with the operation's own schema.
"""

from pathlib import Path

import pytest

from emass_mock import spec
from tests.payloads import control_row, poam_row, result_row

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_packaged_spec_is_the_vendored_spec():
    vendored = REPO_ROOT / "vendor" / "emass_client" / "eMASSRestOpenApi.yaml"
    packaged = Path(spec.spec_path())
    assert packaged.read_bytes() == vendored.read_bytes(), (
        "src/emass_mock/spec/eMASSRestOpenApi.yaml must be a byte-identical copy of "
        "vendor/emass_client/eMASSRestOpenApi.yaml; re-copy it after a vendor update"
    )


def test_spec_version_is_declared():
    assert spec.spec_version().startswith("v3.")
    assert "updateControlBySystemId" in spec.operation_ids()


def test_every_write_handler_names_a_real_operation():
    from emass_mock.handlers import (
        artifacts,
        baselines,
        controls,
        device_scan_results,
        milestones,
        poams,
        test_results,
    )

    names = [
        controls.OPERATION_PUT,
        controls.OPERATION_GET,
        test_results.OPERATION_POST,
        test_results.OPERATION_GET,
        artifacts.OPERATION_POST,
        artifacts.OPERATION_GET,
        poams.OPERATION_POST,
        poams.OPERATION_PUT,
        poams.OPERATION_DELETE,
        poams.OPERATION_GET,
        poams.OPERATION_GET_ONE,
        milestones.OPERATION_POST,
        milestones.OPERATION_PUT,
        milestones.OPERATION_DELETE,
        milestones.OPERATION_GET,
        milestones.OPERATION_GET_ONE,
        device_scan_results.OPERATION_POST,
    ]
    for surface in (baselines.HARDWARE, baselines.SOFTWARE):
        names += [surface.get_op, surface.post_op, surface.put_op, surface.delete_op]
    for name in names:
        spec.operation(name)


def test_test_results_reject_cci_in_request(client, headers):
    resp = client.post(
        "/api/systems/1/test-results",
        json=[result_row(cci="000001")],
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    message = resp.json()["meta"]["errorMessage"]
    assert "addTestResultsBySystemId" in message
    assert "cci" in message


def test_test_results_reject_missing_required_fields(client, headers):
    resp = client.post(
        "/api/systems/1/test-results",
        json=[{"testedBy": "auditor"}],
        headers=headers,
    )
    assert resp.status_code == 400
    message = resp.json()["meta"]["errorMessage"]
    for field in ("testDate", "description", "complianceStatus", "assessmentProcedure"):
        assert field in message


def test_controls_reject_missing_required_fields(client, headers):
    resp = client.put("/api/systems/1/controls", json=[{"acronym": "AC-2"}], headers=headers)
    assert resp.status_code == 400
    assert "responsibleEntities" in resp.json()["meta"]["errorMessage"]


def test_controls_reject_bad_enum(client, headers):
    resp = client.put(
        "/api/systems/1/controls",
        json=[control_row("AC-2", controlDesignation="Shared")],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "controlDesignation" in resp.json()["meta"]["errorMessage"]


def test_controls_reject_wrong_type(client, headers):
    resp = client.put(
        "/api/systems/1/controls",
        json=[control_row("AC-2", estimatedCompletionDate="2026-07-22")],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "estimatedCompletionDate" in resp.json()["meta"]["errorMessage"]


def test_controls_reject_unknown_field(client, headers):
    resp = client.put(
        "/api/systems/1/controls",
        json=[control_row("AC-2", pretorinControlId="abc")],
        headers=headers,
    )
    assert resp.status_code == 400
    assert "pretorinControlId" in resp.json()["meta"]["errorMessage"]


def test_unknown_fields_can_be_allowed(monkeypatch):
    monkeypatch.setenv("EMASS_MOCK_UNKNOWN_FIELDS", "allow")
    assert spec.validate_request("updateControlBySystemId", [control_row("AC-2", extra=1)]) == []
    monkeypatch.setenv("EMASS_MOCK_UNKNOWN_FIELDS", "reject")
    assert spec.validate_request("updateControlBySystemId", [control_row("AC-2", extra=1)])


def test_nullable_conditional_fields_accept_null():
    rows = [control_row("AC-2", naJustification=None)]
    assert spec.validate_request("updateControlBySystemId", rows) == []


def test_body_must_be_an_array(client, headers):
    resp = client.post("/api/systems/1/poams", json=poam_row(), headers=headers)
    assert resp.status_code == 400
    assert "array" in resp.json()["meta"]["errorMessage"]


def test_poam_post_requires_spec_fields(client, headers):
    resp = client.post("/api/systems/1/poams", json=[{"description": "Fix SC-7"}], headers=headers)
    assert resp.status_code == 400
    message = resp.json()["meta"]["errorMessage"]
    assert "status" in message and "pocOrganization" in message


def test_poam_put_requires_ids(client, headers):
    resp = client.put("/api/systems/1/poams", json=[poam_row()], headers=headers)
    assert resp.status_code == 400
    assert "poamId" in resp.json()["meta"]["errorMessage"]


def test_hw_baseline_requires_asset_name(client, headers):
    resp = client.post("/api/systems/1/hw-baseline", json=[{"nickname": "x"}], headers=headers)
    assert resp.status_code == 400
    assert "assetName" in resp.json()["meta"]["errorMessage"]


@pytest.mark.parametrize(
    "operation_id",
    [
        "updateControlBySystemId",
        "addTestResultsBySystemId",
        "addPoamBySystemId",
        "updatePoamBySystemId",
        "deletePoam",
        "addMilestoneBySystemIdAndPoamId",
        "updateMilestoneBySystemIdAndPoamId",
        "deleteMilestone",
        "addHwBaselineAssets",
        "updateHwBaselineAssets",
        "deleteHwBaselineAssets",
        "addSwBaselineAssets",
        "updateSwBaselineAssets",
        "deleteSwBaselineAssets",
    ],
)
def test_array_level_required_is_hoisted_into_items(operation_id):
    """The spec puts ``required`` on the array; the compiled schema binds it to rows."""
    compiled = spec.compile_schema(spec.request_body_schema(operation_id))
    assert compiled["type"] == "array"
    assert "required" not in compiled
    raw_required = spec.request_body_schema(operation_id).get("required", [])
    assert set(raw_required) <= set(compiled["items"].get("required", []))
