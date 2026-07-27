"""Regression tests: preflight covers config-enabled optional tools and engine resource integrity.

Covers two real-run failures:
1. An optional tool enabled via config (e.g. ``plasmid_binning.tools: [scapp]``) was
   skipped by preflight because it is not ``required: true``, so a missing
   executable only surfaced at execution time.
2. A resource directory that exists but fails the engine's per-database
   integrity check (e.g. genomad without its ``genomad_db`` subdirectory) was
   reported ready because preflight only did ``path.exists()``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from abi.internal import _enabled_optional_tool_ids, _run_generic_preflight
from abi.plugins.metagenomic_plasmid._engine.skills.registry import (
    ToolRegistry,
    _resource_status,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLASMID_PLUGIN_ROOT = REPO_ROOT / "plugins" / "metagenomic_plasmid"

GENOMAD_METADATA = {
    "id": "genomad",
    "name": "geNomad",
    "env_name": "autoplasm-plasmid-detect",
    "executable": "genomad",
    "command_template": "genomad end-to-end --cleanup --restart --threads {threads} "
    "{assembly} {output_dir} {database}",
}


def _plugin_with_dag_root(check_tools_fn):
    """Mock plugin exposing the real plasmid plugin DAG root."""
    return SimpleNamespace(
        build_sample_context=lambda config, check_files: SimpleNamespace(samples=[]),
        plugin_id="metagenomic_plasmid",
        root=PLASMID_PLUGIN_ROOT,
        registry=lambda: SimpleNamespace(check_tools=check_tools_fn),
    )


class TestEnabledOptionalToolIds:
    def test_scapp_enabled_via_config(self):
        plugin = SimpleNamespace(root=PLASMID_PLUGIN_ROOT)
        config = {"plasmid_binning": {"tools": ["scapp"]}}
        assert "scapp" in _enabled_optional_tool_ids(plugin, config)

    def test_scapp_not_enabled_by_default(self):
        plugin = SimpleNamespace(root=PLASMID_PLUGIN_ROOT)
        assert "scapp" not in _enabled_optional_tool_ids(plugin, {})

    def test_plugin_without_root_returns_empty_set(self):
        config = {"plasmid_binning": {"tools": ["scapp"]}}
        assert _enabled_optional_tool_ids(SimpleNamespace(), config) == set()


class TestPreflightEnabledOptionalTools:
    @staticmethod
    def _check_tools(config):
        return [
            {
                "tool_id": "scapp",
                "installed": False,
                "resource_status": "not_required",
                "required": False,
            },
            {
                "tool_id": "plasme",
                "installed": False,
                "resource_status": "ok",
                "required": False,
            },
        ]

    def test_enabled_optional_tool_appears_in_preflight(self):
        plugin = _plugin_with_dag_root(self._check_tools)
        config = {"plasmid_binning": {"tools": ["scapp"]}}
        result = _run_generic_preflight(plugin, config, check_runtime=True)

        tool_checks = {c["name"]: c for c in result["checks"] if c["name"].startswith("tool:")}
        assert "tool:scapp" in tool_checks
        # Missing executable on an enabled tool must fail preflight.
        assert tool_checks["tool:scapp"]["status"] == "fail"
        assert result["status"] == "fail"

    def test_disabled_optional_tool_stays_unchecked(self):
        plugin = _plugin_with_dag_root(self._check_tools)
        config = {"plasmid_binning": {"tools": ["scapp"]}}
        result = _run_generic_preflight(plugin, config, check_runtime=True)

        tool_checks = {c["name"]: c for c in result["checks"] if c["name"].startswith("tool:")}
        assert "tool:plasme" not in tool_checks

    def test_no_optional_enabled_keeps_legacy_behaviour(self):
        plugin = _plugin_with_dag_root(self._check_tools)
        result = _run_generic_preflight(plugin, {}, check_runtime=True)

        tool_checks = [c for c in result["checks"] if c["name"].startswith("tool:")]
        assert tool_checks == []
        assert result["status"] == "pass"


class TestGenomadResourceIntegrity:
    def test_directory_without_genomad_db_is_not_ready(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTOPLASM_MAMBA_ROOT", str(tmp_path / ".mamba"))
        database = tmp_path / "genomad"
        database.mkdir()
        config = {"resources": {"genomad": {"database": str(database)}}}

        registry = ToolRegistry([dict(GENOMAD_METADATA)])
        rows = registry.check_tools(config=config)
        assert rows[0]["resource_status"] == "missing"

    def test_directory_with_genomad_db_is_ready(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTOPLASM_MAMBA_ROOT", str(tmp_path / ".mamba"))
        database = tmp_path / "genomad"
        (database / "genomad_db").mkdir(parents=True)
        config = {"resources": {"genomad": {"database": str(database)}}}

        registry = ToolRegistry([dict(GENOMAD_METADATA)])
        rows = registry.check_tools(config=config)
        assert rows[0]["resource_status"] == "ok"

    def test_unregistered_tool_falls_back_to_existence(self, tmp_path):
        database = tmp_path / "db"
        database.mkdir()
        metadata = {"id": "unknown_tool", "command_template": "unknown_tool {database}"}
        status, _ = _resource_status(
            metadata, {"resources": {"unknown_tool": {"database": str(database)}}}
        )
        assert status == "ok"
