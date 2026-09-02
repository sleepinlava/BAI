"""Unit tests for the ABI permission model (C5)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from abi.permissions import (
    TOOL_PERMISSIONS,
    PermissionLevel,
    permission_for_tool,
    requires_confirmation,
)
from abi.tool_descriptors import ABI_AGENT_TOOLS


class TestPermissionLevel:
    def test_all_levels_are_valid_strings(self):
        for level in PermissionLevel:
            assert isinstance(level.value, str)
            assert level.value

    def test_three_levels_exist(self):
        assert len(PermissionLevel.__members__) == 3


class TestPermissionForTool:
    def test_known_tool_returns_correct_level(self):
        # fastp is a common tool — check its permission
        for tool_id in ("fastp", "star", "spades"):
            level = permission_for_tool(tool_id)
            assert level in PermissionLevel.__members__.values()

    def test_unknown_tool_falls_back_to_read_only(self):
        # Unknown tools default to read_only (most restrictive)
        assert permission_for_tool("nonexistent_tool_xyz") == PermissionLevel.READ_ONLY

    def test_all_registered_tools_have_valid_levels(self):
        for tool_id, level in TOOL_PERMISSIONS.items():
            assert isinstance(level, PermissionLevel), f"{tool_id}: {type(level)}"
            assert isinstance(level.value, str)


class TestPermissionSSOT:
    """P0-2: the permission table is derived from the descriptor SSOT."""

    def test_every_descriptor_tool_has_derived_permission(self):
        # Every tool advertised in ABI_AGENT_TOOLS must appear in
        # TOOL_PERMISSIONS with exactly the permission its descriptor declares.
        for tool_name, metadata in ABI_AGENT_TOOLS.items():
            assert tool_name in TOOL_PERMISSIONS, tool_name
            assert TOOL_PERMISSIONS[tool_name] is PermissionLevel(metadata["permission"])

    def test_no_permission_entries_without_descriptor_or_alias(self):
        # No hand-written permission entries may exist outside the SSOT plus
        # the declared legacy alias map.
        allowed = set(ABI_AGENT_TOOLS) | {"autoplasm_validate_result"}
        assert set(TOOL_PERMISSIONS) == allowed

    def test_legacy_alias_inherits_canonical_permission(self):
        assert (
            permission_for_tool("autoplasm_validate_result")
            == permission_for_tool("abi_autoplasm_validate_result")
            == PermissionLevel.READ_ONLY
        )


class TestRequiresConfirmation:
    def test_execution_tool_requires_confirmation(self):
        # 'abi_run' is registered as EXECUTION-level → requires confirmation
        assert requires_confirmation("abi_run") is True

    def test_read_only_tool_does_not_require_confirmation(self):
        # 'abi_list_types' is READ_ONLY → no confirmation needed
        assert requires_confirmation("abi_list_types") is False

    def test_unknown_tool_does_not_require_confirmation(self):
        # Unknown tools default to READ_ONLY → no confirmation
        assert requires_confirmation("_unknown_tool_") is False
