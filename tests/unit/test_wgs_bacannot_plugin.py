from __future__ import annotations

import gzip
from pathlib import Path

import pytest
import yaml

from abi.interfaces import ABIExternalWorkflowPlugin
from abi.plugins import get_plugin
from abi.plugins.wgs_bacannot.process_map import load_process_contracts, map_process_class

PINNED_SHA = "a78ddb0bffe75139adf1f443260d6d5b1987fe27"


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    read1 = tmp_path / "S1_R1.fastq.gz"
    read2 = tmp_path / "S1_R2.fastq.gz"
    read1.write_bytes(gzip.compress(b"@r1\nACGT\n+\nFFFF\n"))
    read2.write_bytes(gzip.compress(b"@r2\nTGCA\n+\nFFFF\n"))
    sheet = tmp_path / "samples.tsv"
    sheet.write_text(
        f"sample_id\tplatform\tread1\tread2\nS1\tillumina\t{read1}\t{read2}\n",
        encoding="utf-8",
    )
    return sheet, read1, read2


def test_plugin_builds_one_managed_external_workflow_parent(tmp_path: Path) -> None:
    sheet, _, _ = _inputs(tmp_path)
    database = tmp_path / "bacannot_db"
    database.mkdir()
    plugin = get_plugin("wgs_bacannot")
    config = plugin.load_config(
        overrides={
            "outdir": str(tmp_path / "results"),
            "input": {"sample_sheet": str(sheet)},
            "resources": {"bacannot_db": str(database)},
        }
    )

    plan = plugin.build_plan(config)
    spec = plugin.external_workflow_spec(config, plan)

    assert isinstance(plugin, ABIExternalWorkflowPlugin)
    assert plan.analysis_type == "wgs_bacannot"
    assert len(plan.steps) == 1
    assert plan.steps[0].step_id == "bacannot_workflow"
    assert spec.commit_sha == PINNED_SHA
    assert spec.expected_process_classes == ("assembly", "annotation", "mlst", "amr")
    assert "-r" in spec.argv and PINNED_SHA in spec.argv
    assert spec.argv[spec.argv.index("--skip_sourmash") + 1] == "true"


def test_samplesheet_conversion_is_safe_and_deterministic(tmp_path: Path) -> None:
    sheet, read1, read2 = _inputs(tmp_path)
    plugin = get_plugin("wgs_bacannot")
    destination = tmp_path / "bacannot_samplesheet.yaml"

    first = plugin.convert_sample_sheet(sheet, destination, check_files=True)
    second = plugin.convert_sample_sheet(sheet, destination, check_files=True)

    payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert payload == {"samplesheet": [{"id": "S1", "illumina": [str(read1), str(read2)]}]}
    assert first.sha256 == second.sha256


def test_samplesheet_rejects_duplicate_files_and_unsafe_ids(tmp_path: Path) -> None:
    sheet, read1, _ = _inputs(tmp_path)
    sheet.write_text(
        f"sample_id\tplatform\tread1\tread2\n../escape\tillumina\t{read1}\t{read1}\n",
        encoding="utf-8",
    )
    plugin = get_plugin("wgs_bacannot")

    with pytest.raises(ValueError, match="sample_id|same physical file"):
        plugin.convert_sample_sheet(sheet, tmp_path / "output.yaml", check_files=True)


@pytest.mark.parametrize(
    ("process_name", "expected"),
    [
        ("BACANNOT:UNICYCLER", "assembly"),
        ("BACANNOT:PROKKA", "annotation"),
        ("BACANNOT:MLST", "mlst"),
        ("BACANNOT:AMRFINDER", "amr"),
        ("BACANNOT:NEW_UPSTREAM_PROCESS", "unmapped"),
    ],
)
def test_fixed_revision_process_mapping(process_name: str, expected: str) -> None:
    plugin = get_plugin("wgs_bacannot")
    assert (
        map_process_class(process_name, load_process_contracts(plugin.root / "process_contracts"))
        == expected
    )


def test_unknown_config_key_is_rejected() -> None:
    plugin = get_plugin("wgs_bacannot")
    with pytest.raises(ValueError, match="Unknown wgs_bacannot config key"):
        plugin.load_config(overrides={"workflow": {"arbitrary_nextflow_flag": True}})


def test_invalid_config_type_is_rejected() -> None:
    plugin = get_plugin("wgs_bacannot")
    with pytest.raises(ValueError, match="max_cpus"):
        plugin.load_config(overrides={"resources": {"max_cpus": "many"}})


def test_unsupported_revision_fails_before_execution(tmp_path: Path) -> None:
    sheet, _, _ = _inputs(tmp_path)
    plugin = get_plugin("wgs_bacannot")

    with pytest.raises(ValueError, match="Unsupported Bacannot revision"):
        plugin.load_config(
            overrides={
                "input": {"sample_sheet": str(sheet)},
                "workflow": {"revision": "master", "commit_sha": "moving"},
            }
        )
