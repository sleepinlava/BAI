"""Frozen Agent-facing schemas for neutral study workspace operations."""

from __future__ import annotations

from typing import Any

WORKSPACE_OPERATION_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_files": {
        "description": "List files below an allowed /task/input or /task/work directory.",
        "required": ["visible_root"],
        "properties": {"visible_root": {"type": "string"}},
    },
    "read_text": {
        "description": "Read an allowed text, JSON, TSV, or YAML file.",
        "required": ["visible_path"],
        "properties": {"visible_path": {"type": "string"}},
    },
    "write_json": {
        "description": "Write a task-requested JSON object below /task/work.",
        "required": ["visible_path", "payload"],
        "properties": {
            "visible_path": {"type": "string"},
            "payload": {"type": "object"},
        },
    },
    "copy_config": {
        "description": "Copy an allowed JSON/YAML config from input to work.",
        "required": ["source", "destination"],
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
        },
    },
    "edit_config": {
        "description": "Apply top-level JSON/YAML updates to a config below /task/work.",
        "required": ["visible_path", "updates"],
        "properties": {
            "visible_path": {"type": "string"},
            "updates": {"type": "object"},
        },
    },
    "request_execution": {
        "description": "Request execution authorization for an explicit config path.",
        "required": ["config_path"],
        "properties": {"config_path": {"type": "string"}},
    },
    "execute_tool": {
        "description": (
            "Execute one frozen tool shim with the named real-contract arguments and outputs. "
            "Fault behavior is controlled privately and cannot be selected by the Agent."
        ),
        "required": ["tool_id", "config_path", "arguments", "outputs"],
        "properties": {
            "tool_id": {"type": "string"},
            "config_path": {"type": "string"},
            "arguments": {"type": "object"},
            "outputs": {"type": "object", "additionalProperties": {"type": "string"}},
            "authorization_token": {"type": ["string", "null"]},
        },
    },
    "inspect_status": {
        "description": "Inspect process-event counts and current work outputs.",
        "required": [],
        "properties": {},
    },
    "abi_call": {
        "description": (
            "Call the production ABI Agent interface for discovery, planning, preflight, "
            "dry-run, or validation. Real execution remains the common execute_tool operation."
        ),
        "required": ["tool_name", "arguments"],
        "properties": {
            "tool_name": {
                "type": "string",
                "enum": [
                    "list_types",
                    "query",
                    "plan",
                    "check",
                    "dry_run",
                    "inspect",
                    "abi_validate_result",
                ],
            },
            "arguments": {"type": "object"},
        },
    },
}


def schemas_for_operations(operations: list[str]) -> dict[str, Any]:
    """Render one deterministic JSON-Schema-like descriptor per mounted operation."""
    return {
        operation: {
            "type": "object",
            **WORKSPACE_OPERATION_SCHEMAS[operation],
            "additionalProperties": False,
        }
        for operation in operations
    }
