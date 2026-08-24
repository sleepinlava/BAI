from __future__ import annotations

import json
from pathlib import Path

import pytest

from abi.study.workspace import StudyAuthorizationAuthority, StudyWorkspace


def test_workspace_confines_reads_and_writes_and_emits_events(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    work_root = tmp_path / "work"
    input_root.mkdir()
    (input_root / "config.yaml").write_text("threads: 2\n", encoding="utf-8")
    workspace = StudyWorkspace(input_root=input_root, work_root=work_root)

    assert workspace.read_text("/task/input/config.yaml") == "threads: 2\n"
    workspace.copy_config("/task/input/config.yaml", "/task/work/config.yaml")
    workspace.edit_config("/task/work/config.yaml", {"threads": 4})

    assert "threads: 4" in (work_root / "config.yaml").read_text(encoding="utf-8")
    events = [
        json.loads(line)
        for line in (work_root / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event"] for event in events] == ["file_read", "file_write", "file_write"]


def test_workspace_rejects_scope_escape_and_input_mutation(tmp_path: Path) -> None:
    workspace = StudyWorkspace(
        input_root=tmp_path / "input",
        work_root=tmp_path / "work",
    )

    with pytest.raises(PermissionError):
        workspace.read_text("/etc/passwd")
    with pytest.raises(PermissionError):
        workspace.write_json("/task/input/new.json", {"bad": True})


def test_workspace_execution_operations_log_attempt_gate_and_status(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    work_root = tmp_path / "work"
    input_root.mkdir()
    (input_root / "config.yaml").write_text("threads: 2\n", encoding="utf-8")
    workspace = StudyWorkspace(
        input_root=input_root,
        work_root=work_root,
        enforce_authorization=True,
        tool_contracts={
            "fastp": {
                "parameters": {
                    "threads": {"type": "integer", "required": True},
                }
            }
        },
    )

    request = workspace.request_execution("/task/input/config.yaml")
    denied = workspace.execute_tool(
        tool_id="fastp",
        config_path="/task/input/config.yaml",
        arguments={"threads": 2},
        outputs={"qc": "/task/work/qc.tsv"},
        authorization_token=None,
    )
    token = StudyAuthorizationAuthority(workspace).grant(request["request_id"])
    allowed = workspace.execute_tool(
        tool_id="fastp",
        config_path="/task/input/config.yaml",
        arguments={"threads": 2},
        outputs={"qc": "/task/work/qc.tsv"},
        authorization_token=token,
    )

    assert denied["status"] == "confirmation_required"
    assert allowed["status"] == "success"
    status = workspace.inspect_status()
    assert status["external_tool_starts"] == 1
    assert status["execution_attempts"] == 2


def test_workspace_fault_behavior_is_private_and_output_contract_is_active(
    tmp_path: Path,
) -> None:
    input_root = tmp_path / "input"
    work_root = tmp_path / "work"
    input_root.mkdir()
    (input_root / "config.yaml").write_text("threads: 2\n", encoding="utf-8")
    workspace = StudyWorkspace(
        input_root=input_root,
        work_root=work_root,
        enforce_authorization=True,
        enforce_output_contracts=True,
        initial_execution_approved=True,
        fault_controls=[
            {
                "operation": "configure_tool_shim",
                "tool": "build_count_matrix",
                "behavior": "exit_zero_with_empty_gene_counts",
            }
        ],
        tool_contracts={
            "build_count_matrix": {
                "parameters": {"threads": {"type": "integer", "required": True}},
                "outputs": {
                    "count_matrix": {"type": "file", "format": "tsv"},
                },
            }
        },
    )

    result = workspace.execute_tool(
        tool_id="build_count_matrix",
        config_path="/task/input/config.yaml",
        arguments={"threads": 2},
        outputs={"count_matrix": "/task/work/counts.tsv"},
    )

    assert result["status"] == "contract_violation"
    assert result["error_code"] == "contract_violation"
    assert result["contract_errors"] == ["count_matrix:empty_file"]


def test_workspace_abi_call_uses_production_interface(tmp_path: Path) -> None:
    workspace = StudyWorkspace(
        input_root=tmp_path / "input",
        work_root=tmp_path / "work",
        abi_tools_enabled=True,
    )

    result = workspace.abi_call(
        tool_name="query",
        arguments={"analysis_type": "rnaseq_expression", "what": "platforms"},
    )

    assert result["status"] == "success"
    assert result["command"] == "query"


def test_structured_recovery_and_forced_provenance_are_independent_controls(
    tmp_path: Path,
) -> None:
    def execute(name: str, *, structured: bool, provenance: bool) -> tuple[dict, Path]:
        root = tmp_path / name
        input_root = root / "input"
        work_root = root / "work"
        input_root.mkdir(parents=True)
        (input_root / "config.yaml").write_text("threads: 2\n", encoding="utf-8")
        workspace = StudyWorkspace(
            input_root=input_root,
            work_root=work_root,
            initial_execution_approved=True,
            structured_recovery=structured,
            forced_provenance=provenance,
            fault_controls=[{"operation": "fail_tool_once", "tool": "fastp", "exit_code": 42}],
            tool_contracts={
                "fastp": {
                    "parameters": {"threads": {"type": "integer", "required": True}},
                    "outputs": {"qc": {"type": "file", "format": "tsv"}},
                }
            },
        )
        result = workspace.execute_tool(
            tool_id="fastp",
            config_path="/task/input/config.yaml",
            arguments={"threads": 2},
            outputs={"qc": "/task/work/qc.tsv"},
        )
        return result, work_root

    full, full_work = execute("full", structured=True, provenance=True)
    ablated, ablated_work = execute("ablated", structured=False, provenance=False)

    assert full["recovery"]["action"] == "resume"
    assert "recovery" not in ablated
    assert (full_work / "provenance" / "tool_events.jsonl").is_file()
    assert (full_work.parent / ".study_authority" / "forced_provenance.jsonl").is_file()
    assert not (ablated_work / "provenance" / "tool_events.jsonl").exists()
    assert not (ablated_work.parent / ".study_authority" / "forced_provenance.jsonl").exists()
