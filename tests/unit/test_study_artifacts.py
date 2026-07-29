from __future__ import annotations

import json
from pathlib import Path

from abi.study.artifacts import build_contract_snapshot, render_advisory_card
from abi.study.operation_schemas import schemas_for_operations

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_contract_snapshot_captures_agent_visible_workflow_contract() -> None:
    snapshot = build_contract_snapshot(REPO_ROOT, "rnaseq_expression")

    assert snapshot["schema_version"] == "abi.control-validation.contract-snapshot.v1"
    assert snapshot["plugin"]["analysis_type"] == "rnaseq_expression"
    assert snapshot["stages"]
    assert snapshot["dag_edges"]
    assert {tool["id"] for tool in snapshot["tools"]} >= {"fastp", "star", "deseq2"}
    assert snapshot["output_contracts"]
    assert snapshot["error_categories"]
    assert snapshot["standard_tables"]
    assert snapshot["limitations"]


def test_advisory_card_is_deterministic_and_derived_from_snapshot() -> None:
    snapshot = build_contract_snapshot(REPO_ROOT, "wgs_bacteria")

    first = render_advisory_card(snapshot)
    second = render_advisory_card(json.loads(json.dumps(snapshot)))

    assert first == second
    assert snapshot["plugin"]["display_name"] in first
    assert all(stage["id"] in first for stage in snapshot["stages"])
    assert all(platform in first for platform in snapshot["platforms"])
    assert all(tool["name"] in first for tool in snapshot["tools"])
    assert "gold" not in first.lower()
    assert "fault location" not in first.lower()


def test_execution_schema_does_not_allow_agent_selected_fault_behavior() -> None:
    schemas = schemas_for_operations(["execute_tool"])

    assert "behavior" not in schemas["execute_tool"]["properties"]
    assert schemas["execute_tool"]["additionalProperties"] is False
