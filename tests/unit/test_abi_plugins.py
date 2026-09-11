import inspect
from pathlib import Path

import pytest

import abi.plugins as plugin_registry
from abi.agent import ABIAgentInterface
from abi.plugins import (
    PluginLoadError,
    PluginSelectionError,
    get_plugin,
    list_plugin_metadata,
    list_plugins,
)
from abi.testing import assert_plugin_contract
from abi.tool_descriptors import ABI_AGENT_TOOLS, TOOL_ALIASES, export_openai_tools

FIXTURES = Path("tests/fixtures/tool_outputs")


class _RegistryTestPlugin:
    plugin_id = "registry_test"
    display_name = "Registry Test"
    description = "Test-only plugin."
    report_title = "Registry Test Report"

    def load_config(self, config_path=None, *, profile=None, db_profile=None, overrides=None):
        return {}

    def build_plan(self, config, check_files=True):
        return None

    def registry(self):
        from abi.tools import ToolRegistry

        return ToolRegistry({})

    def table_schemas(self):
        return {}

    def parse_outputs(self, tool_id, output_dir, sample_id):
        return {}

    def write_report(self, plan, result_dir):
        return {}


class _FakeEntryPoint:
    def __init__(self, name, value="", plugin_class=None, error=None):
        self.name = name
        self.value = value
        self._plugin_class = plugin_class
        self._error = error

    def load(self):
        if self._error:
            raise self._error
        return self._plugin_class


def test_abi_lists_builtin_plugins():
    plugin_ids = {plugin.plugin_id for plugin in list_plugins()}

    assert "metagenomic_plasmid" in plugin_ids
    assert "metatranscriptomics" in plugin_ids


def test_metatranscriptomics_plan_uses_plugin_schema(tmp_path):
    plugin = get_plugin("metatranscriptomics")
    config = plugin.load_config(overrides={"outdir": str(tmp_path / "results")})

    plan = plugin.build_plan(config)

    assert plan.analysis_type == "metatranscriptomics"
    assert [step.tool_id for step in plan.steps] == ["fastp", "star", "featurecounts"]
    # DAG planner resolves genome_index from config resources into inputs
    assert "genome_index" in plan.steps[1].inputs
    assert "gene_expression" in plugin.table_schemas()
    assert Path(plan.outdir) == tmp_path / "results"


def test_metatranscriptomics_null_alignment_uses_default_aligner(tmp_path):
    plugin = get_plugin("metatranscriptomics")
    config = plugin.load_config(overrides={"outdir": str(tmp_path / "results"), "alignment": None})
    config["alignment"] = None

    plan = plugin.build_plan(config)

    assert plan.steps[1].tool_id == "star"


def test_metagenomic_plasmid_plugin_parses_standard_outputs():
    plugin = get_plugin("metagenomic_plasmid")

    rows = plugin.parse_outputs("genomad", FIXTURES / "genomad", "S1")

    assert rows["plasmid_predictions"]
    assert rows["plasmid_predictions"][0]["sample_id"] == "S1"
    assert rows["plasmid_predictions"][0]["tool"] == "genomad"


@pytest.mark.parametrize(
    ("tool_id", "source_table", "public_table"),
    [
        ("bakta", "annotations", "plasmid_annotation"),
        ("coverm", "abundance", "plasmid_abundance"),
    ],
)
def test_metagenomic_plasmid_plugin_expands_public_standard_tables(
    tool_id, source_table, public_table
):
    plugin = get_plugin("metagenomic_plasmid")

    rows = plugin.parse_outputs(tool_id, FIXTURES / tool_id, "S1")

    assert rows[source_table]
    assert rows[public_table]


def test_builtin_plugins_satisfy_machine_contracts():
    for plugin_id in (
        "metatranscriptomics",
        "metagenomic_plasmid",
        "rnaseq_expression",
        "wgs_bacteria",
        "amplicon_16s",
    ):
        assert_plugin_contract(get_plugin(plugin_id))


def test_inline_plugins_implement_dry_run_protocol():
    from abi.interfaces import ABIDryRunPlugin

    for plugin_id in (
        "metatranscriptomics",
        "rnaseq_expression",
        "wgs_bacteria",
        "amplicon_16s",
    ):
        assert isinstance(get_plugin(plugin_id), ABIDryRunPlugin)


def test_metagenomic_plasmid_uses_plugin_local_registry():
    plugin = get_plugin("metagenomic_plasmid")

    registry = plugin.registry()

    assert registry.has("genomad")
    assert (plugin.root / "tool_registry.yaml").exists()


def test_metagenomic_plasmid_contracts_cover_every_registered_tool():
    plugin = get_plugin("metagenomic_plasmid")
    registry_ids = set(plugin.registry().ids())
    contract_ids = {path.stem for path in (plugin.root / "tool_contracts").glob("*.yaml")}

    assert registry_ids == contract_ids


def test_abi_discovers_entry_point_plugins(monkeypatch):
    class FakePlugin:
        plugin_id = "fake_analysis"
        display_name = "Fake Analysis"
        description = "Test-only plugin."
        report_title = "Fake Analysis Report"

        def load_config(self, config_path=None, *, profile=None, db_profile=None, overrides=None):
            return {}

        def build_plan(self, config, check_files=True):
            from abi.schemas import ExecutionPlan

            return ExecutionPlan(pipeline_id="fake", steps=[])

        def registry(self):
            from abi.tools import ToolRegistry

            return ToolRegistry({})

        def table_schemas(self):
            return {}

        def parse_outputs(self, tool_id, output_dir, sample_id):
            return {}

        def write_report(self, plan, result_dir):
            return {}

    class FakeEntryPoint:
        name = "fake_analysis"

        def load(self):
            return FakePlugin

    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [FakeEntryPoint()])

    assert get_plugin("fake_analysis").display_name == "Fake Analysis"
    plugin_ids = {plugin.plugin_id for plugin in list_plugins()}
    assert {"fake_analysis", "metagenomic_plasmid", "metatranscriptomics"} <= plugin_ids


def test_abi_skips_broken_entry_point_plugins(monkeypatch):
    class BrokenEntryPoint:
        name = "broken"

        def load(self):
            raise ImportError("broken import")

    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [BrokenEntryPoint()])

    with pytest.warns(RuntimeWarning, match="Skipping ABI plugin entry point"):
        plugin_ids = {plugin.plugin_id for plugin in list_plugins()}

    assert "broken" not in plugin_ids
    assert {"metagenomic_plasmid", "metatranscriptomics"} <= plugin_ids


def test_metadata_discovery_does_not_load_entry_points(monkeypatch):
    entry_point = _FakeEntryPoint(
        "metadata_only",
        "missing.module:Plugin",
        error=AssertionError("metadata discovery imported implementation"),
    )
    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [entry_point])

    metadata = {item.plugin_id: item for item in list_plugin_metadata()}

    assert metadata["metadata_only"].metadata_available is False
    assert metadata["metadata_only"].entry_point == "missing.module:Plugin"


def test_selected_plugin_ignores_unrelated_entry_point_failure(monkeypatch):
    monkeypatch.setattr(_RegistryTestPlugin, "plugin_id", "selected")
    good = _FakeEntryPoint(
        "selected", "tests.unit.test_abi_plugins:_RegistryTestPlugin", _RegistryTestPlugin
    )
    broken = _FakeEntryPoint("unrelated", "broken.module:Plugin", error=ImportError("broken"))
    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [broken, good])

    assert get_plugin("selected").plugin_id == "selected"


def test_selected_plugin_failure_is_explicit(monkeypatch):
    broken = _FakeEntryPoint(
        "selected_failure", "broken.module:Plugin", error=ImportError("broken")
    )
    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [broken])

    with pytest.raises(PluginLoadError, match="selected_failure"):
        get_plugin("selected_failure")


def test_competing_entry_points_fail_deterministically(monkeypatch):
    first = _FakeEntryPoint("collision", "one.module:Plugin", _RegistryTestPlugin)
    second = _FakeEntryPoint("collision", "two.module:Plugin", _RegistryTestPlugin)
    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [second, first])

    with pytest.raises(PluginSelectionError, match="competing implementations"):
        get_plugin("collision")


def test_manifest_and_different_entry_point_do_not_get_silently_merged(monkeypatch, tmp_path):
    plugin_root = tmp_path / "plugins"
    manifest_root = plugin_root / "manifested"
    manifest_root.mkdir(parents=True)
    (manifest_root / "abi-plugin.yaml").write_text(
        "\n".join(
            [
                'abi_version: "0.1"',
                "plugin_id: manifested",
                "display_name: Manifested",
                "description: Manifested plugin",
                "report_title: Manifested report",
                "entry_point: one.module:Plugin",
            ]
        ),
        encoding="utf-8",
    )
    competing = _FakeEntryPoint("manifested", "two.module:Plugin", _RegistryTestPlugin)
    monkeypatch.setattr(plugin_registry, "PLUGIN_ROOT", plugin_root)
    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [competing])

    metadata = next(item for item in list_plugin_metadata() if item.plugin_id == "manifested")

    assert metadata.status == "conflict"
    with pytest.raises(PluginSelectionError, match="competing implementations"):
        get_plugin("manifested")


def test_invalid_manifest_cannot_be_bypassed_by_entry_point(monkeypatch, tmp_path):
    plugin_root = tmp_path / "plugins"
    manifest_root = plugin_root / "invalid"
    manifest_root.mkdir(parents=True)
    (manifest_root / "abi-plugin.yaml").write_text("plugin_id: invalid\n", encoding="utf-8")
    invalid = _FakeEntryPoint("invalid", "invalid.module:Plugin", _RegistryTestPlugin)
    monkeypatch.setattr(plugin_registry, "PLUGIN_ROOT", plugin_root)
    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [invalid])

    with pytest.raises(PluginLoadError, match="invalid manifest metadata"):
        get_plugin("invalid")


def test_competing_manifests_fail_without_entry_points(monkeypatch, tmp_path):
    plugin_root = tmp_path / "plugins"
    for directory, target in (("one", "one.module:Plugin"), ("two", "two.module:Plugin")):
        manifest_root = plugin_root / directory
        manifest_root.mkdir(parents=True)
        (manifest_root / "abi-plugin.yaml").write_text(
            "\n".join(
                [
                    'abi_version: "0.1"',
                    "plugin_id: duplicated",
                    "display_name: Duplicated",
                    "description: Duplicated plugin",
                    "report_title: Duplicated report",
                    f"entry_point: {target}",
                ]
            ),
            encoding="utf-8",
        )
    monkeypatch.setattr(plugin_registry, "PLUGIN_ROOT", plugin_root)
    monkeypatch.setattr(plugin_registry, "_entry_points", lambda: [])

    with pytest.raises(PluginSelectionError, match="competing implementations"):
        get_plugin("duplicated")


def test_openai_tool_export_uses_agent_permissions_and_keeps_execution_opt_in():
    plugin = get_plugin("metagenomic_plasmid")

    tools = export_openai_tools(plugin, descriptor_format="responses")

    names = {tool["name"] for tool in tools}
    assert "abi_validate_result" in names
    assert "abi_export_agent_context" in names
    assert "abi_doctor_agent" in names
    assert "abi_run" not in names
    for tool in tools:
        assert tool["strict"] is True
        assert tool["parameters"]["additionalProperties"] is False

    apps_tools = export_openai_tools(plugin, descriptor_format="apps-sdk")
    apps_by_name = {tool["name"]: tool for tool in apps_tools}
    assert "abi_run" not in apps_by_name
    assert apps_by_name["abi_plan"]["inputSchema"]["additionalProperties"] is False
    assert apps_by_name["abi_inspect"]["annotations"]["readOnlyHint"] is True
    assert apps_by_name["abi_export_agent_context"]["annotations"]["readOnlyHint"] is True

    json_tools = export_openai_tools(
        plugin,
        descriptor_format="json",
        include_execution=True,
    )
    by_name = {tool["name"]: tool for tool in json_tools}
    assert by_name["abi_inspect"]["permission"] == "read_only"
    assert by_name["abi_report"]["permission"] == "planning_write"
    assert by_name["abi_run"]["permission"] == "execution"
    assert by_name["abi_run"]["requires_confirmation"] is True


def test_openai_tool_schemas_cover_agent_interface_parameters():
    # Build mapping from SSOT: only abi_* tool names that have corresponding
    # ABIAgentInterface methods (excludes legacy autoplasm alias).
    mapping = {
        name: TOOL_ALIASES[name]
        for name in ABI_AGENT_TOOLS
        if name in TOOL_ALIASES and not name.startswith("autoplasm")
    }

    for tool_name, method_name in mapping.items():
        signature = inspect.signature(getattr(ABIAgentInterface, method_name))
        method_params = {name for name in signature.parameters if name != "self"}
        schema_params = set(ABI_AGENT_TOOLS[tool_name]["properties"])

        # Bidirectional equality (P0-3): a one-directional subset check let
        # descriptors advertise parameters the method does not accept — the
        # mismatch only surfaced at runtime as a TypeError error envelope.
        # 双向相等: 单向子集检查允许描述符广告方法不接受的参数,
        # 差异只会在运行时以 TypeError 错误信封暴露。
        assert method_params == schema_params, (
            f"{tool_name}: method-only={sorted(method_params - schema_params)}, "
            f"schema-only={sorted(schema_params - method_params)}"
        )
