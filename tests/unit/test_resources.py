import json
from pathlib import Path

from abi.plugins.metagenomic_plasmid.lib.config import load_config as load_autoplasm_config
from abi.plugins.metagenomic_plasmid.lib.resources import (
    check_resources,
    required_resource_issues,
    setup_resources,
)
from abi.resources import check_resources as check_abi_resources
from abi.resources import setup_resources as setup_abi_resources


def test_setup_resources_mock_writes_manifest(tmp_path):
    config = {"resources": {"root": str(tmp_path / "resources")}}

    rows = setup_resources(config, resource_ids=["genomad", "bakta"], mock=True)

    assert {row["resource_id"] for row in rows} == {"genomad", "bakta"}
    assert all(row["status"] == "ok" for row in rows)
    assert all(row["mock"] is True for row in rows)
    assert (tmp_path / "resources" / "resources.json").exists()
    genomad = check_resources(config, resource_ids=["genomad"])[0]
    assert genomad["status"] == "ok"
    assert genomad["ready_check"] == "ready sentinel found"
    assert genomad["directory_file_count"] >= 1
    assert "directory_size_bytes" in genomad


def test_database_profile_resource_paths_rebase_to_resource_root(tmp_path):
    resource_root = tmp_path / "custom-resources"

    config = load_autoplasm_config(
        db_profile="light",
        overrides={"resources": {"root": str(resource_root)}},
    )
    rows = check_resources(config, resource_ids=["genomad", "bakta"])

    paths = {row["resource_id"]: Path(row["path"]) for row in rows}
    assert paths == {
        "genomad": resource_root / "genomad" / "genomad_db",
        "bakta": resource_root / "bakta" / "db",
    }


def test_wgs_mock_resource_uses_safe_outdir_for_placeholder_path(tmp_path):
    config = {
        "outdir": str(tmp_path / "results"),
        "resources": {"amrfinder_db": "/path/to/amrfinderplus/database"},
    }

    rows = setup_abi_resources(
        analysis_type="wgs_bacteria",
        config=config,
        resource_ids=["amrfinder_db"],
        mock=True,
    )

    target = tmp_path / "results" / "resources" / "amrfinder_db"
    assert rows[0]["path"] == str(target)
    assert (target / ".abi_resource.json").is_file()


def test_rnaseq_resource_filter_is_exact():
    config = {
        "resources": {
            "annotation_gtf": "ANNOTATION_GTF_NOT_CONFIGURED",
            "genome_index": "GENOME_INDEX_NOT_CONFIGURED",
        }
    }

    rows = check_abi_resources(
        analysis_type="rnaseq_expression",
        config=config,
        resource_ids=["annotation_gtf"],
    )

    assert [row["resource_id"] for row in rows] == ["annotation_gtf"]


def test_setup_resources_reports_progress(tmp_path):
    config = {"resources": {"root": str(tmp_path / "resources")}}
    events = []

    setup_resources(
        config,
        resource_ids=["genomad"],
        mock=True,
        progress_callback=lambda event, resource_id, message: events.append(
            (event, resource_id, message)
        ),
    )

    assert events[0] == ("start", "genomad", "preparing")
    assert events[-1] == ("finish", "genomad", "ok")


def test_plasmidfinder_uses_current_database_url(tmp_path):
    config = {"resources": {"root": str(tmp_path / "resources")}}

    rows = setup_resources(config, resource_ids=["plasmidfinder"], dry_run=True)

    assert "https://bitbucket.org/genomicepidemiology/plasmidfinder_db.git" in rows[0]["command"]
    assert rows[0]["source_url"].endswith("plasmidfinder_db.git")


def test_required_resource_issues_for_selected_tools(tmp_path):
    config = {"resources": {"root": str(tmp_path / "resources")}}

    issues = required_resource_issues(config, ["genomad", "bakta"])

    assert len(issues) == 2
    assert "genomad.database" in issues[0]


def test_metaphlan_resource_is_required_when_selected(tmp_path):
    config = {"resources": {"root": str(tmp_path / "resources")}}

    issues = required_resource_issues(config, ["metaphlan"])

    assert len(issues) == 1
    assert "metaphlan.database" in issues[0]


def test_metaphlan_resource_is_included_in_default_setup(tmp_path):
    config = {"resources": {"root": str(tmp_path / "resources")}}

    rows = setup_resources(config, dry_run=True)

    assert "metaphlan" in {row["resource_id"] for row in rows}


def test_wgs_resource_setup_has_real_dry_run_and_mock_paths(tmp_path):
    config = {
        "outdir": str(tmp_path / "wgs"),
        "resources": {"amrfinder_db": "AMRFINDER_DB_NOT_CONFIGURED"},
    }

    planned = setup_abi_resources(analysis_type="wgs_bacteria", config=config, dry_run=True)
    mocked = setup_abi_resources(analysis_type="wgs_bacteria", config=config, mock=True)

    assert planned[0]["status"] == "planned"
    assert planned[0]["mock"] is False
    assert planned[0]["command"][0] == "amrfinder_update"
    assert mocked[0]["status"] == "ok"
    assert mocked[0]["mock"] is True
    assert Path(mocked[0]["path"]).is_dir()


def test_metatranscriptomics_resource_setup_is_actionable_without_build_choice(tmp_path):
    config = {
        "outdir": str(tmp_path / "meta"),
        "resources": {
            "genome_index": "GENOME_INDEX_NOT_CONFIGURED",
            "annotation_gtf": "ANNOTATION_GTF_NOT_CONFIGURED",
        },
    }

    rows = setup_abi_resources(analysis_type="metatranscriptomics", config=config)

    assert {row["resource_id"] for row in rows} == {"genome_index", "annotation_gtf"}
    assert {row["status"] for row in rows} == {"manual_required"}


def test_metatranscriptomics_mock_resources_create_expected_shapes(tmp_path):
    config = {
        "outdir": str(tmp_path / "meta"),
        "resources": {
            "genome_index": "GENOME_INDEX_NOT_CONFIGURED",
            "annotation_gtf": "ANNOTATION_GTF_NOT_CONFIGURED",
        },
    }

    rows = setup_abi_resources(analysis_type="metatranscriptomics", config=config, mock=True)
    paths = {row["resource_id"]: Path(row["path"]) for row in rows}

    assert paths["genome_index"].is_dir()
    assert paths["annotation_gtf"].is_file()


def test_large_plugin_resource_bundles_report_manual_and_support_mock(tmp_path):
    for analysis_type, resource_id in (
        ("easymetagenome", "kraken2_db"),
        ("viral_viwrap", "db_dir"),
    ):
        config = {
            "outdir": str(tmp_path / analysis_type),
            "resources": {resource_id: f"{resource_id.upper()}_NOT_CONFIGURED"},
        }
        manual = setup_abi_resources(analysis_type=analysis_type, config=config)
        mocked = setup_abi_resources(analysis_type=analysis_type, config=config, mock=True)

        assert manual[0]["status"] == "manual_required"
        assert mocked[0]["status"] == "ok"
        assert Path(mocked[0]["path"]).is_dir()


def test_core_resource_orchestrator_delegates_to_plugin_capability(monkeypatch):
    calls = []

    class ResourcePlugin:
        def check_resources(self, config, *, resource_ids=None):
            calls.append(("check", config, resource_ids))
            return [{"status": "checked"}]

        def setup_resources(self, config, *, resource_ids=None, dry_run=False, mock=False):
            calls.append(("setup", config, resource_ids, dry_run, mock))
            return [{"status": "planned"}]

    monkeypatch.setattr("abi.resources.get_plugin", lambda analysis_type: ResourcePlugin())

    assert check_abi_resources(
        analysis_type="external", config={"value": 1}, resource_ids=["db"]
    ) == [{"status": "checked"}]
    assert setup_abi_resources(
        analysis_type="external",
        config={"value": 2},
        resource_ids=["db"],
        dry_run=True,
        mock=True,
    ) == [{"status": "planned", "mock": True}]
    assert calls == [
        ("check", {"value": 1}, ["db"]),
        ("setup", {"value": 2}, ["db"], True, True),
    ]


def test_core_resource_orchestrator_has_generic_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("abi.resources.get_plugin", lambda analysis_type: object())
    database = tmp_path / "db"
    database.mkdir()
    config = {"outdir": str(tmp_path), "resources": {"database": str(database)}}

    checked = check_abi_resources(analysis_type="external", config=config)
    planned = setup_abi_resources(analysis_type="external", config=config, dry_run=True)

    assert checked[0]["status"] == "incomplete"
    assert planned[0]["status"] == "planned"


# ---- New tests for Level 1 + Level 2 resources (2026-06-20) ----


def test_level1_resources_included_in_default_setup(tmp_path):
    """All Level 1 (auto_setup=True) resources appear in default dry-run."""
    config = {"resources": {"root": str(tmp_path / "resources")}}
    rows = setup_resources(config, dry_run=True)
    ids = {row["resource_id"] for row in rows}

    assert "genomad" in ids
    assert "bakta" in ids
    assert "mob_suite" in ids
    assert "plasmidfinder" in ids
    assert "metaphlan" in ids
    assert "amrfinderplus" in ids
    assert "kraken2" in ids
    assert "gtdbtk" in ids
    assert "checkm2" in ids
    # Level 1 = 9 databases + 4 auto-install tools = 13
    assert len(rows) == 14


def test_level2_resources_excluded_from_default_setup(tmp_path):
    """Level 2 (auto_setup=False) resources are skipped in default setup."""
    config = {"resources": {"root": str(tmp_path / "resources")}}
    rows = setup_resources(config, dry_run=True)
    ids = {row["resource_id"] for row in rows}

    assert "plasme" not in ids
    assert "plasx_annotations" not in ids
    assert "plasx_model" not in ids
    assert "copla_refgraph" not in ids
    assert "copla_reflist" not in ids
    assert "blast" not in ids
    assert "plasmidhostfinder" not in ids
    # Level 2 tool specs also excluded
    assert "plasmaag_tool" not in ids
    assert "gplas2_tool" not in ids
    assert "scapp_tool" not in ids
    assert "recycler_tool" not in ids
    assert "copla_tool" not in ids
    assert "plasmidhostfinder_tool" not in ids
    assert "conjscan_tool" not in ids


def test_level2_resources_appear_in_check_resources(tmp_path):
    """Level 2 resources are reported by check_resources with missing status."""
    config = {"resources": {"root": str(tmp_path / "resources")}}
    rows = check_resources(config)
    ids = {row["resource_id"] for row in rows}

    assert "plasme" in ids
    assert "plasx_annotations" in ids
    assert "plasx_model" in ids
    assert "copla_refgraph" in ids
    assert "copla_reflist" in ids
    assert "blast" in ids
    assert "plasmidhostfinder" in ids


def test_level2_resources_report_missing_status(tmp_path):
    """Level 2 resources with no path configured report 'missing' status."""
    config = {"resources": {"root": str(tmp_path / "resources")}}
    rows = check_resources(config)

    for row in rows:
        if row["resource_id"] == "plasme":
            assert row["status"] == "missing"
            assert "PLASMe" in row.get("source_url", "")


def test_level2_resource_can_be_explicitly_selected(tmp_path):
    """An auto_setup=False resource is included when explicitly selected."""
    config = {"resources": {"root": str(tmp_path / "resources")}}
    rows = setup_resources(config, resource_ids=["plasme"], dry_run=True)
    ids = {row["resource_id"] for row in rows}

    assert "plasme" in ids
    assert len(rows) == 1


def test_amrfinderplus_required_resource_issues(tmp_path):
    """required_resource_issues detects missing amrfinderplus database."""
    config = {"resources": {"root": str(tmp_path / "resources")}}
    issues = required_resource_issues(config, ["amrfinderplus"])

    assert len(issues) >= 1
    assert any("amrfinderplus.database" in i for i in issues)


def test_all_resources_in_check_resources(tmp_path):
    """check_resources returns every registered database and tool resource."""
    config = {"resources": {"root": str(tmp_path / "resources")}}
    rows = check_resources(config)
    ids = {row["resource_id"] for row in rows}

    assert len(ids) == 30
    expected_db = {
        "genomad",
        "bakta",
        "mob_suite",
        "plasmidfinder",
        "metaphlan",
        "amrfinderplus",
        "card",
        "kraken2",
        "gtdbtk",
        "checkm2",
        "eggnog_mapper",
        "abricate",
        "plasme",
        "plasx_annotations",
        "plasx_model",
        "copla_refgraph",
        "copla_reflist",
        "blast",
        "plasmidhostfinder",
    }
    expected_tools = {
        "plasme_tool",
        "plasx_tool",
        "platon_tool",
        "macsyfinder_tool",
        "plasmaag_tool",
        "gplas2_tool",
        "scapp_tool",
        "recycler_tool",
        "copla_tool",
        "plasmidhostfinder_tool",
        "conjscan_tool",
    }
    assert ids == expected_db | expected_tools


# ── Regression tests for download-hardening fixes (Phase 4) ───────────────


def test_kraken2_command_is_safe_list_form(tmp_path):
    """M1: kraken2 download must not use `bash -c` with raw path interpolation."""
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        _resolved_resource_command,
        default_resource_specs,
    )

    config = {"resources": {"root": str(tmp_path / "resources")}}
    spec = next(s for s in default_resource_specs(config) if s.resource_id == "kraken2")
    path = tmp_path / "resources" / "kraken2"
    command = _resolved_resource_command(config, spec, path)

    assert command[0] != "bash"
    assert "bash" not in command
    assert "-c" not in command
    assert command[0] == "aria2c"


def test_kraken2_url_uses_config_version(tmp_path):
    """M5: kraken2 URL version must be configurable, not hardcoded."""
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        _kraken2_version,
        default_resource_specs,
    )

    config = {
        "resources": {
            "root": str(tmp_path / "resources"),
            "kraken2": {"version": "standard_20240115"},
        }
    }
    spec = next(s for s in default_resource_specs(config) if s.resource_id == "kraken2")
    assert _kraken2_version(config, spec) == "standard_20240115"

    # Falls back to spec default when version is a placeholder.
    config_placeholder = {
        "resources": {
            "root": str(tmp_path / "resources"),
            "kraken2": {"version": "KRAKEN2_VERSION_NOT_CONFIGURED"},
        }
    }
    assert _kraken2_version(config_placeholder, spec) == "standard_20260226"


def test_tool_download_command_does_not_double_path(tmp_path):
    """M3: tool_download command must not append default_subdir twice."""
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        _resolved_resource_command,
        default_resource_specs,
    )

    config = {"resources": {"root": str(tmp_path / "resources")}}
    spec = next(s for s in default_resource_specs(config) if s.resource_id == "copla_tool")
    # _configured_resource_path already appends default_subdir → root/COPLA
    path = tmp_path / "resources" / "COPLA"
    command = _resolved_resource_command(config, spec, path)

    assert command[0] == "wget"
    assert command[1] == "-O"
    # The -O target should be path/executable, NOT path/default_subdir/executable.
    out_target = Path(command[2])
    assert out_target == path / spec.executable


def test_git_clone_uses_shallow_depth(tmp_path):
    """m2: git clone commands must use --depth 1 --single-branch."""
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        _resolved_resource_command,
        default_resource_specs,
    )

    config = {"resources": {"root": str(tmp_path / "resources")}}
    spec = next(s for s in default_resource_specs(config) if s.resource_id == "plasmidfinder")
    path = tmp_path / "resources" / "plasmidfinder_db"
    command = _resolved_resource_command(config, spec, path)

    assert command[:3] == ["git", "clone", "--depth"]
    assert "1" in command
    assert "--single-branch" in command


def test_tool_git_ready_check_validates_worktree(tmp_path):
    """M10: a partial git clone (only .git, no valid HEAD) must not be 'ready'."""
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        _resource_path_ready,
        default_resource_specs,
    )

    config = {"resources": {"root": str(tmp_path / "resources")}}
    spec = next(s for s in default_resource_specs(config) if s.resource_id == "plasmidfinder")
    path = tmp_path / "fake_clone"
    path.mkdir()
    (path / ".git").mkdir()  # partial clone: .git exists but no valid worktree

    assert not _resource_path_ready(path, spec)


def test_mob_suite_ready_check_rejects_sentinel_only(tmp_path):
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        _resource_path_ready,
        default_resource_specs,
    )

    config = {"resources": {"root": str(tmp_path / "resources")}}
    spec = next(s for s in default_resource_specs(config) if s.resource_id == "mob_suite")
    path = tmp_path / "mob_suite"
    path.mkdir()
    (path / ".autoplasm_resource_ready").touch()
    (path / "repetitive.dna.fas.nhr").write_text("index", encoding="utf-8")

    assert not _resource_path_ready(path, spec)


def test_mob_suite_ready_check_requires_complete_runtime_database(tmp_path):
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        MOB_SUITE_REQUIRED_FILES,
        _resource_path_ready,
        default_resource_specs,
    )

    config = {"resources": {"root": str(tmp_path / "resources")}}
    spec = next(s for s in default_resource_specs(config) if s.resource_id == "mob_suite")
    path = tmp_path / "mob_suite"
    path.mkdir()
    for name in MOB_SUITE_REQUIRED_FILES:
        (path / name).write_text("ready", encoding="utf-8")
    (path / "repetitive.dna.fas.nhr").write_text("index", encoding="utf-8")

    assert _resource_path_ready(path, spec)


def test_kraken2_version_constant_referenced():
    """KRAKEN2_DEFAULT_VERSION must be the single source for the default
    Kraken2 snapshot date — referenced by both the ResourceSpec default and
    the _kraken2_version fallback, so updating it in one place suffices."""
    from abi.plugins.metagenomic_plasmid.lib.resources import (
        KRAKEN2_DEFAULT_VERSION,
        _kraken2_version,
        default_resource_specs,
    )

    # The constant is non-empty and looks like a dated snapshot.
    assert KRAKEN2_DEFAULT_VERSION.startswith("standard_")
    # The kraken2 ResourceSpec uses the constant as its default version.
    spec = next(s for s in default_resource_specs({}) if s.resource_id == "kraken2")
    assert spec.version == KRAKEN2_DEFAULT_VERSION
    # _kraken2_version falls back to the same constant when config is empty.
    assert _kraken2_version({}, spec) == KRAKEN2_DEFAULT_VERSION


def test_abi_setup_resources_reports_manual_requirements_without_downloading(tmp_path):
    """WP8: `abi setup-resources` reports readiness/manual guidance and never
    downloads. The old --confirm download gate retired with the downloads."""
    from typer.testing import CliRunner

    from abi.cli import app

    runner = CliRunner()
    config = tmp_path / "config.yaml"
    config.write_text(
        "resources:\n  root: " + str(tmp_path / "resources") + "\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "setup-resources",
            "--type",
            "metagenomic_plasmid",
            "--config",
            str(config),
        ],
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows
    assert all(row["status"] in {"ok", "manual_required", "not_configured"} for row in rows)
    assert any(row["status"] == "manual_required" for row in rows)
    # --dry-run still plans without touching anything.
    result_dry = runner.invoke(
        app,
        [
            "setup-resources",
            "--type",
            "metagenomic_plasmid",
            "--config",
            str(config),
            "--dry-run",
        ],
    )
    assert result_dry.exit_code == 0
    assert all(row["status"] == "planned" for row in json.loads(result_dry.output))


def test_check_resources_reports_ready_and_incomplete_databases(tmp_path):
    """Protected behaviors moved from the retired setup download path: the
    check path classifies ready vs incomplete databases without downloading."""
    resource_root = tmp_path / "resources"
    (resource_root / "genomad" / "genomad_db").mkdir(parents=True)
    config = {"resources": {"root": str(resource_root)}}

    ready_rows = check_resources(config, resource_ids=["genomad"])
    assert ready_rows[0]["status"] == "ok"
    assert ready_rows[0]["ready_check"] == "genomad_db directory found"

    incomplete_root = tmp_path / "incomplete"
    (incomplete_root / "genomad").mkdir(parents=True)
    config2 = {"resources": {"root": str(incomplete_root)}}
    incomplete_rows = check_resources(config2, resource_ids=["genomad"])
    assert incomplete_rows[0]["status"] == "incomplete"


def test_setup_resources_reports_manual_required_without_downloading(tmp_path):
    """WP8: real-run setup reports external preparation requirements and
    never downloads; ready resources still report ok."""
    resource_root = tmp_path / "resources"
    (resource_root / "genomad" / "genomad_db").mkdir(parents=True)
    config = {"resources": {"root": str(resource_root)}}

    rows = setup_resources(config, resource_ids=["genomad"])

    assert rows[0]["status"] == "ok"
    assert (resource_root / "resources.json").is_file()

    empty_root = tmp_path / "empty"
    config2 = {"resources": {"root": str(empty_root)}}
    rows2 = setup_resources(config2, resource_ids=["genomad"])
    assert rows2[0]["status"] == "manual_required"
    assert "External preparation required" in rows2[0]["message"]
    # nothing was downloaded/fabricated into the resource path
    assert not (empty_root / "genomad" / "genomad_db").exists()
