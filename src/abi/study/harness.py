"""Transport-neutral trial preparation for the ABI validation harness."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import yaml

from abi.study.operation_schemas import schemas_for_operations
from abi.study.workspace import StudyWorkspace


def prepare_trial(
    *,
    study: Mapping[str, Any],
    tasks: Mapping[str, Any],
    study_root: Path,
    fixture_root: Path,
    interface_root: Path,
    task_id: str,
    condition: str,
    model_id: str,
    seed: int,
    artifact_root: Path,
) -> dict[str, Any]:
    """Prepare one condition-isolated filesystem request without invoking a model."""
    task = next(
        (item for item in tasks["tasks"] if str(item["task_id"]) == task_id),
        None,
    )
    if task is None:
        raise ValueError(f"Unknown task: {task_id}")
    if condition not in study["conditions"]:
        raise ValueError(f"Unknown condition: {condition}")

    clean_relative = Path(str(task["base_fixture"]["clean_twin"])).relative_to("fixtures")
    fault_relative = clean_relative.with_name(clean_relative.name.removesuffix("_clean") + "_fault")
    source = fixture_root / fault_relative / "input"
    if not source.exists():
        raise FileNotFoundError("Fixture not built; run abi-study build-artifacts first")
    artifact_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source, artifact_root / "input")
    (artifact_root / "work").mkdir()
    (artifact_root / "interface").mkdir()
    authority_root = artifact_root / ".study_authority"
    authority_root.mkdir()

    if condition == "matched_advisory":
        shutil.copyfile(
            interface_root / "advisory_cards" / f"{task['workflow']}.md",
            artifact_root / "interface" / "advisory_card.md",
        )
    else:
        shutil.copyfile(
            interface_root / "contract_snapshot" / f"{task['workflow']}.json",
            artifact_root / "interface" / "contract_snapshot.json",
        )
    shutil.copyfile(
        interface_root / "tool_shims" / "manifest.json",
        artifact_root / "interface" / "tool_shims.json",
    )
    shutil.copyfile(
        interface_root / "tool_shims" / "golden_contracts.json",
        artifact_root / "interface" / "tool_contracts.json",
    )
    condition_spec = study["conditions"][condition]
    control_source = fixture_root / fault_relative / "fixture_control.json"
    fault_controls = (
        json.loads(control_source.read_text(encoding="utf-8")) if control_source.exists() else []
    )
    initial_approved = task["authorization"] == "execution_approved_in_initial_prompt"
    (authority_root / "runtime_control.json").write_text(
        json.dumps(
            {
                "workflow": task["workflow"],
                "fault_controls": fault_controls,
                "initial_execution_approved": initial_approved,
                "active_preflight_contracts": condition_spec["active_preflight_contracts"],
                "active_authorization_gate": condition_spec["active_authorization_gate"],
                "active_output_contracts": condition_spec["active_output_contracts"],
                "structured_recovery": condition_spec["structured_recovery"],
                "forced_provenance": condition_spec["forced_provenance"],
                "abi_tools_enabled": condition_spec["knowledge_surface"] == "abi_agent_tools",
                "preflight_resource_ids": _preflight_resource_ids(
                    study_root, task["base_fixture"]["recipe"]
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    available_operations = [
        "list_files",
        "read_text",
        "write_json",
        "copy_config",
        "edit_config",
        "request_execution",
        "execute_tool",
        "inspect_status",
    ]
    if condition_spec["knowledge_surface"] == "abi_agent_tools":
        available_operations.append("abi_call")
    (artifact_root / "interface" / "interface.json").write_text(
        json.dumps(
            {
                "condition_label": condition_spec["label_for_agent"],
                "knowledge_surface": condition_spec["knowledge_surface"],
                "workspace_entrypoint": "abi.study.workspace:StudyWorkspace",
                "available_operations": available_operations,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (artifact_root / "interface" / "operation_schemas.json").write_text(
        json.dumps(
            schemas_for_operations(available_operations),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    request = {
        "schema_version": "abi.control-validation.request.v1",
        "study_id": study["study_id"],
        "task_id": task_id,
        "condition": condition,
        "condition_label": study["conditions"][condition]["label_for_agent"],
        "model_id": model_id,
        "seed": seed,
        "system_prompt": (study_root / "system_prompt.txt").read_text(encoding="utf-8"),
        "user_prompt": task["visible_prompt"],
        "budget": study["budget"],
        "runner_status": "awaiting_frozen_model_adapter",
    }
    (artifact_root / "request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "status": "prepared",
        "trial_root": str(artifact_root),
        "next": (
            "A frozen model adapter must consume request.json and write "
            "transcript.jsonl plus final_response.json."
        ),
    }


def invoke_workspace_operation(
    *,
    trial_root: Path,
    operation: str,
    arguments: Mapping[str, Any],
) -> Any:
    """Dispatch one allow-listed advisory workspace operation."""
    control = json.loads(
        (trial_root / ".study_authority" / "runtime_control.json").read_text(encoding="utf-8")
    )
    contracts = json.loads(
        (trial_root / "interface" / "tool_contracts.json").read_text(encoding="utf-8")
    )
    workspace = StudyWorkspace(
        input_root=trial_root / "input",
        work_root=trial_root / "work",
        enforce_authorization=bool(control["active_authorization_gate"]),
        enforce_preflight_contracts=bool(control["active_preflight_contracts"]),
        enforce_output_contracts=bool(control["active_output_contracts"]),
        initial_execution_approved=bool(control["initial_execution_approved"]),
        abi_tools_enabled=bool(control["abi_tools_enabled"]),
        workflow=str(control["workflow"]),
        fault_controls=list(control["fault_controls"]),
        preflight_resource_ids=set(control["preflight_resource_ids"]),
        tool_contracts=contracts,
    )
    workspace.record_interface_call(operation, arguments)
    try:
        if operation == "list_files":
            return workspace.list_files(**dict(arguments))
        if operation == "read_text":
            return workspace.read_text(**dict(arguments))
        if operation == "write_json":
            return workspace.write_json(**dict(arguments))
        if operation == "copy_config":
            return workspace.copy_config(**dict(arguments))
        if operation == "edit_config":
            return workspace.edit_config(**dict(arguments))
        if operation == "request_execution":
            return workspace.request_execution(**dict(arguments))
        if operation == "execute_tool":
            return workspace.execute_tool(**dict(arguments))
        if operation == "inspect_status":
            return workspace.inspect_status()
        if operation == "abi_call":
            return workspace.abi_call(**dict(arguments))
        raise ValueError(f"Unsupported workspace operation: {operation}")
    except PermissionError:
        workspace.record_scope_violation(operation)
        raise


def _preflight_resource_ids(study_root: Path, recipe_id: str) -> list[str]:
    recipes = yaml.safe_load((study_root / "fixture_recipes.yaml").read_text(encoding="utf-8"))
    return list(recipes["recipes"][recipe_id].get("preflight_resource_ids", []))
