import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from abi.agent import ABIAgentInterface, interface


def test_agent_interface_lists_types_with_success_envelope():
    payload = json.loads(ABIAgentInterface().list_types())

    assert payload["status"] == "success"
    assert payload["command"] == "list_types"
    assert payload["result"]["count"] >= 2
    names = {row["analysis_type"] for row in payload["result"]["analysis_types"]}
    assert {"metagenomic_plasmid", "metatranscriptomics"} <= names


def test_agent_interface_plan_writes_plan_with_uniform_result(tmp_path):
    outdir = tmp_path / "agent_plan"

    payload = json.loads(
        ABIAgentInterface().plan(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "log"),
        )
    )

    assert payload["status"] == "success"
    assert payload["command"] == "plan"
    assert payload["result"]["analysis_type"] == "metatranscriptomics"
    assert payload["result"]["steps"] == 3
    assert payload["result"]["written_files"] == [
        str(outdir / "execution_plan.json"),
        str(outdir / "compiled_plan.json"),
    ]
    assert payload["result"]["compiled_plan_path"] == str(outdir / "compiled_plan.json")
    assert (outdir / "execution_plan.json").exists()
    assert (outdir / "compiled_plan.json").exists()


def test_agent_interface_run_requires_confirmation():
    payload = json.loads(
        ABIAgentInterface().run(
            analysis_type="metatranscriptomics",
            outdir="results/agent-confirmation-only",
            log_dir="log",
            smoke=True,
        )
    )

    assert payload["status"] == "confirmation_required"
    assert payload["command"] == "run"
    assert payload["result"]["message"].startswith("Re-run with confirm_execution=true")


@pytest.mark.parametrize(
    "confirm_execution",
    ["false", "true", 1, ["approved"], {"approved": True}],
)
def test_agent_interface_run_rejects_truthy_non_boolean_confirmation_before_prepare(
    monkeypatch, confirm_execution
):
    coordinator_factory = Mock(name="WorkflowCoordinator")
    monkeypatch.setattr(interface, "WorkflowCoordinator", coordinator_factory)

    payload = json.loads(
        ABIAgentInterface().run(
            analysis_type="metatranscriptomics",
            confirm_execution=confirm_execution,
        )
    )

    assert payload["status"] == "confirmation_required"
    assert payload["command"] == "run"
    coordinator_factory.assert_not_called()


def test_agent_interface_run_accepts_boolean_true(monkeypatch):
    prepared = SimpleNamespace(
        plan=object(),
        config={"outdir": "results/agent-boolean-true"},
    )
    bound_ids: list[str] = []

    class StubCoordinator:
        def prepare(self, *args, **kwargs):
            return prepared

        def run(self, received_prepared):
            assert received_prepared is prepared
            return SimpleNamespace(status="success", return_code=0, outputs={})

    monkeypatch.setattr(interface, "WorkflowCoordinator", StubCoordinator)

    def _fake_bind(received_prepared):
        assert received_prepared is prepared
        bound_ids.append("sha256:stub")
        return bound_ids[-1]

    monkeypatch.setattr(interface, "bind_confirmed_plan", _fake_bind)

    payload = json.loads(
        ABIAgentInterface().run(
            analysis_type="metatranscriptomics",
            confirm_execution=True,
        )
    )

    assert payload["status"] == "success"
    assert payload["result"]["runtime_status"] == "success"
    assert bound_ids == ["sha256:stub"]


def test_agent_interface_reports_invalid_json_file(tmp_path):
    result_dir = tmp_path / "bad_result"
    result_dir.mkdir()
    (result_dir / "execution_plan.json").write_text("{bad json\n", encoding="utf-8")

    payload = json.loads(ABIAgentInterface(verbose_errors=True).report(result_dir=result_dir))

    assert payload["status"] == "error"
    assert payload["error_code"] == "parse_failed"
    assert payload["error_type"] == "ABIJSONError"
    assert payload["diagnostic_hints"]
    assert "Invalid JSON in" in payload["error"]


def test_agent_interface_errors_include_diagnostics(tmp_path):
    payload = json.loads(
        ABIAgentInterface().plan(
            analysis_type="metatranscriptomics",
            sample_sheet=str(tmp_path / "missing.tsv"),
            outdir=str(tmp_path / "agent_plan"),
            log_dir=str(tmp_path / "log"),
        )
    )

    assert payload["status"] == "error"
    assert payload["error_code"] == "missing_input"
    assert payload["diagnostic_hints"][0]["code"] == "missing_input"
    assert payload["diagnostic_hints"][0]["suggested_next_action"]


def test_agent_interface_exports_agent_context():
    payload = json.loads(
        ABIAgentInterface().export_agent_context(analysis_type="metatranscriptomics")
    )

    assert payload["status"] == "success"
    assert payload["command"] == "export_agent_context"
    assert payload["result"]["analysis_type"] == "metatranscriptomics"
    assert payload["result"]["execution_requires_confirmation"] is True
    assert payload["result"]["safe_sequence"][-1] == "report"
    assert "abi_run" in payload["result"]["unsafe_tools"]
    assert "abi_run" not in payload["result"]["default_exported_tools"]
    assert "gene_expression" in payload["result"]["standard_tables"]


def test_agent_interface_doctor_agent_returns_short_guide():
    payload = json.loads(ABIAgentInterface().doctor_agent(analysis_type="metatranscriptomics"))

    assert payload["status"] == "success"
    assert payload["result"]["analysis_type"] == "metatranscriptomics"
    assert "Canonical lifecycle" in payload["result"]["text"]
    assert "request_authorization -> run" in payload["result"]["text"]
    assert "abi_validate_result -> report" in payload["result"]["text"]


def test_agent_interface_dispatch_accepts_cli_style_tool_aliases():
    agent = ABIAgentInterface()

    context = json.loads(
        agent.dispatch("export-agent-context", {"analysis_type": "metatranscriptomics"})
    )
    doctor = json.loads(agent.dispatch("doctor-agent", {"analysis_type": "metatranscriptomics"}))
    list_types = json.loads(agent.dispatch("list-types", {}))

    assert context["status"] == "success"
    assert context["command"] == "export_agent_context"
    assert doctor["status"] == "success"
    assert doctor["command"] == "doctor_agent"
    assert list_types["status"] == "success"
    assert list_types["command"] == "list_types"


def test_agent_dispatch_enforces_execution_permission_before_handler(monkeypatch):
    agent = ABIAgentInterface()

    def unexpected_run(**kwargs):
        raise AssertionError(f"run handler should not be called: {kwargs}")

    monkeypatch.setattr(agent, "run", unexpected_run)
    payload = json.loads(agent.dispatch("run", {"analysis_type": "metatranscriptomics"}))

    assert payload["status"] == "confirmation_required"
    assert payload["result"]["tool"] == "abi_run"


@pytest.mark.parametrize(
    "confirm_execution",
    ["false", "true", 1, ["approved"], {"approved": True}],
)
def test_agent_dispatch_rejects_truthy_non_boolean_confirmation_before_handler(
    monkeypatch, confirm_execution
):
    agent = ABIAgentInterface()
    run_handler = Mock(name="run_handler")
    monkeypatch.setattr(agent, "run", run_handler)
    payload = json.loads(
        agent.dispatch(
            "run",
            {"analysis_type": "metatranscriptomics", "confirm_execution": confirm_execution},
        )
    )

    assert payload["status"] == "confirmation_required"
    assert payload["result"]["tool"] == "abi_run"
    run_handler.assert_not_called()


def test_agent_install_skills_is_dispatchable(tmp_path):
    payload = json.loads(
        ABIAgentInterface().dispatch(
            "abi_install_skills",
            {"target": str(tmp_path / "skills")},
        )
    )

    assert payload["status"] == "success"
    assert payload["command"] == "install_skills"
    assert (tmp_path / "skills" / "README.md").is_file()


def test_autoplasm_result_alias_uses_plugin_validation_capability(monkeypatch, tmp_path):
    calls = []
    plugin = SimpleNamespace(
        validate_result_dir=lambda result_dir, allow_empty_tables=True: (
            calls.append((result_dir, allow_empty_tables)) or {"valid": True}
        )
    )
    monkeypatch.setattr(interface, "get_plugin", lambda plugin_id: plugin)

    payload = json.loads(
        ABIAgentInterface().autoplasm_validate_result(
            result_dir=tmp_path,
            allow_empty_tables=False,
        )
    )

    assert payload["status"] == "success"
    # WP5: the honest plugin-validation flag rides along with the plugin's
    # own validation result.
    # WP5：诚实的插件校验标志随插件自身校验结果一并返回。
    assert payload["result"]["valid"] is True
    assert payload["result"]["plugin_validation_executed"] is True
    assert calls == [(tmp_path, False)]


def test_query_resolves_dag_from_plugin_root_not_global_constant(tmp_path, monkeypatch):
    """11A: query reads the DAG from the selected plugin's own root so an
    externally installed plugin answers without assuming the global root."""
    from abi.plugin_registry import get_plugin

    plugin = get_plugin("metatranscriptomics")
    monkeypatch.setattr(type(plugin), "root", property(lambda self: tmp_path), raising=False)
    (tmp_path / "pipeline_dag.yaml").write_text(
        "nodes: []\n",
        encoding="utf-8",
    )
    (tmp_path / "tool_registry.yaml").write_text(
        "tools:\n- id: fastp\n  default_enabled: true\n  required: true\n",
        encoding="utf-8",
    )

    payload = json.loads(
        ABIAgentInterface().query(analysis_type="metatranscriptomics", what="stages")
    )

    assert payload["status"] == "success"


def _make_result_dir(tmp_path, analysis_type="metatranscriptomics"):
    """Minimal successful result directory (pre-snapshot layout)."""
    outdir = tmp_path / "results"
    (outdir / "provenance").mkdir(parents=True)
    (outdir / "tables").mkdir()
    (outdir / "execution_plan.json").write_text(
        json.dumps({"analysis_type": analysis_type, "project_name": "t", "steps": []}),
        encoding="utf-8",
    )
    (outdir / "provenance" / "run_summary.json").write_text(
        json.dumps({"status": "success", "analysis_type": analysis_type}),
        encoding="utf-8",
    )
    (outdir / "provenance" / "commands.tsv").write_text(
        "step_id\tstatus\ns1\tsuccess\n", encoding="utf-8"
    )
    return outdir


def test_report_falls_back_to_basic_report_without_plugin(tmp_path, monkeypatch):
    """WP5: basic report works with the plugin uninstalled, using saved facts."""
    outdir = _make_result_dir(tmp_path)
    (outdir / "tables" / "qc_summary.tsv").write_text("metric\tvalue\nx\t1\n", encoding="utf-8")

    def _unknown(plugin_id):
        raise ValueError(f"Unknown ABI analysis type: {plugin_id}")

    monkeypatch.setattr("abi.agent.interface.get_plugin", _unknown)

    payload = json.loads(
        ABIAgentInterface().report(result_dir=str(outdir), analysis_type="metatranscriptomics")
    )

    assert payload["status"] == "success"
    assert payload["result"]["plugin_report_generated"] is False
    assert payload["result"]["plugin_available"] is False
    assert payload["result"]["audit_snapshot_found"] is False
    written = [Path(p) for p in payload["result"]["written_files"]]
    assert written and all(p.exists() for p in written)
    report_md = (outdir / "report" / "report.md").read_text(encoding="utf-8")
    assert "Audit snapshot missing" in report_md


def test_report_uses_audit_snapshot_limitations_without_plugin(tmp_path, monkeypatch):
    outdir = _make_result_dir(tmp_path)
    (outdir / "provenance" / "audit_snapshot.json").write_text(
        json.dumps(
            {
                "schema_version": "abi.audit_snapshot.v1",
                "analysis_type": "metatranscriptomics",
                "report_title": "Tx Report",
                "limitations": ["mock limitation for audit"],
                "standard_table_schemas": {"qc_summary": ["metric", "value"]},
            }
        ),
        encoding="utf-8",
    )

    def _unknown(plugin_id):
        raise ValueError(f"Unknown ABI analysis type: {plugin_id}")

    monkeypatch.setattr("abi.agent.interface.get_plugin", _unknown)

    payload = json.loads(
        ABIAgentInterface().report(result_dir=str(outdir), analysis_type="metatranscriptomics")
    )

    assert payload["status"] == "success"
    assert payload["result"]["audit_snapshot_found"] is True
    report_md = (outdir / "report" / "report.md").read_text(encoding="utf-8")
    assert "mock limitation for audit" in report_md
    assert "Tx Report" in report_md


def test_validate_result_falls_back_to_structural_checks_without_plugin(tmp_path, monkeypatch):
    """WP5: structural validation runs without the plugin and never implies
    plugin-specific scientific validation happened."""
    outdir = _make_result_dir(tmp_path)

    def _unknown(plugin_id):
        raise ValueError(f"Unknown ABI analysis type: {plugin_id}")

    monkeypatch.setattr("abi.plugin_registry.get_plugin", _unknown)

    payload = json.loads(
        ABIAgentInterface().abi_validate_result(result_dir=str(outdir), allow_empty_tables=True)
    )

    # The minimal fixture lacks full artifacts, so structural errors are
    # expected; the contract under test is the honest plugin-validation flag.
    # 最小夹具缺完整产物，结构错误属预期；被测契约是诚实的插件校验标志。
    assert payload["status"] == "success"
    result = payload["result"]
    # Without the plugin and without a snapshot, schema-based checks report
    # the gap honestly instead of silently passing.
    # 无插件且无快照时，基于 schema 的检查如实报告缺失而不是静默通过。
    assert result["schema_source"] == "unavailable"
    assert any("audit snapshot" in error for error in result["errors"])


def test_validate_result_uses_audit_snapshot_schema_without_plugin(tmp_path, monkeypatch):
    """WP5: table-schema checks run from the audit snapshot when the plugin
    that produced them is not installed."""
    outdir = _make_result_dir(tmp_path)
    (outdir / "tables" / "qc_summary.tsv").write_text("metric\tvalue\nx\t1\n", encoding="utf-8")
    (outdir / "provenance" / "audit_snapshot.json").write_text(
        json.dumps(
            {
                "schema_version": "abi.audit_snapshot.v1",
                "analysis_type": "metatranscriptomics",
                "standard_table_schemas": {"qc_summary": ["metric", "value"]},
            }
        ),
        encoding="utf-8",
    )

    def _unknown(plugin_id):
        raise ValueError(f"Unknown ABI analysis type: {plugin_id}")

    monkeypatch.setattr("abi.plugin_registry.get_plugin", _unknown)

    payload = json.loads(ABIAgentInterface().abi_validate_result(result_dir=str(outdir)))

    assert payload["status"] == "success"
    result = payload["result"]
    assert result["schema_source"] == "audit_snapshot"
    assert result["tables"]["qc_summary"]["exists"] is True
    assert result["tables"]["qc_summary"]["missing_fields"] == []
