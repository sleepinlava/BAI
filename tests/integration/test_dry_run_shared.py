"""Shared-path dry-run parity for metagenomic_plasmid (WP2).

These tests replace the old ``PipelineExecutor``-direct dry-run entry: the
plugin's planned-skip status rows must reach ``analysis_status`` through the
shared executor's ``write_run_tables`` hook with identical replace semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from abi.plugins import get_plugin
from abi.runtimes import RuntimeOptions
from abi.workflow import WorkflowCoordinator


def _read_table(tables_dir: Path, name: str) -> list[dict[str, str]]:
    path = tables_dir / f"{name}.tsv"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:]]


def _prepare(tmp_path: Path, *, skipped: list[Any], outdir: Path | None = None) -> Any:
    sheet = tmp_path / "samples.tsv"
    sheet.write_text(
        "sample_id\tplatform\tread1\tread2\n"
        "S1\tillumina\t/data/r1.fq.gz\t/data/r2.fq.gz\n"
        "S2\tillumina\t/data/r3.fq.gz\t/data/r4.fq.gz\n",
        encoding="utf-8",
    )
    overrides = {
        "input": {"sample_sheet": str(sheet)},
        "outdir": str(outdir or tmp_path / "results"),
        "log_dir": str(tmp_path / "log"),
        "mock_tools": True,
    }
    plugin = get_plugin("metagenomic_plasmid")
    config = plugin.load_config(overrides=overrides)
    plan = plugin.build_plan(config, check_files=False)
    plan.skipped_steps = list(skipped)
    coordinator = WorkflowCoordinator()
    prepared = coordinator.prepare(
        "metagenomic_plasmid",
        None,
        overrides=dict(overrides),
        check_files=False,
        options=RuntimeOptions(engine="local"),
    )
    prepared.plan.skipped_steps = list(skipped)
    return coordinator, prepared


def _skipped_diversity() -> Any:
    from abi.schemas import PlanStep

    return PlanStep(
        step_id="diversity_not_run",
        step_name="diversity",
        tool_id="internal",
        category="statistics",
        sample_id=None,
        params={"sample_count": 1, "threshold": 3},
        reason="requires at least 3 samples",
        skipped=True,
    )


def test_shared_dry_run_records_planned_skip_status(tmp_path: Path) -> None:
    coordinator, prepared = _prepare(tmp_path, skipped=[_skipped_diversity()])

    result = coordinator.dry_run(prepared)

    assert result.status == "success"
    tables_dir = Path(str(prepared.config["outdir"])) / "tables"
    rows = _read_table(tables_dir, "analysis_status")
    assert [row["module"] for row in rows] == ["diversity"]
    assert rows[0]["status"] == "not_run"
    assert rows[0]["reason"] == "requires at least 3 samples"
    assert rows[0]["threshold"] == "3"


def test_repeated_shared_dry_run_replaces_analysis_status_rows(tmp_path: Path) -> None:
    coordinator, prepared = _prepare(tmp_path, skipped=[_skipped_diversity()])

    coordinator.dry_run(prepared)
    tables_dir = Path(str(prepared.config["outdir"])) / "tables"
    first_rows = _read_table(tables_dir, "analysis_status")
    coordinator.dry_run(prepared)
    second_rows = _read_table(tables_dir, "analysis_status")

    assert first_rows
    assert second_rows == first_rows


def test_shared_dry_run_writes_standard_provenance(tmp_path: Path) -> None:
    coordinator, prepared = _prepare(tmp_path, skipped=[])

    result = coordinator.dry_run(prepared)

    assert result.status == "success"
    outdir = Path(str(prepared.config["outdir"]))
    assert (outdir / "execution_plan.json").is_file()
    assert (outdir / "provenance" / "commands.tsv").is_file()
    assert (outdir / "provenance" / "run_summary.json").is_file()
    assert (outdir / "provenance" / "audit_snapshot.json").is_file()
    summary = yaml.safe_load((outdir / "provenance" / "run_summary.json").read_text())
    assert summary["analysis_type"] == "metagenomic_plasmid"


def test_shared_dry_run_preserves_existing_output_files(tmp_path: Path) -> None:
    """Repeated dry-runs must not wipe pre-existing files in the outdir."""
    outdir = tmp_path / "results"
    outdir.mkdir()
    marker = outdir / "keep.txt"
    marker.write_text("keep\n", encoding="utf-8")

    coordinator, prepared = _prepare(tmp_path, skipped=[], outdir=outdir)

    result = coordinator.dry_run(prepared)

    assert result.status == "success"
    assert marker.read_text(encoding="utf-8") == "keep\n"
    assert (outdir / "execution_plan.json").is_file()


def test_shared_dry_run_resolved_plan_matches_planned_steps(tmp_path: Path) -> None:
    """The resolved-plan snapshot records executed I/O truth with the same
    step inventory as the pre-run plan."""
    import json as jsonlib

    coordinator, prepared = _prepare(tmp_path, skipped=[])
    outdir = Path(str(prepared.config["outdir"]))

    result = coordinator.dry_run(prepared)

    assert result.status == "success"
    resolved = jsonlib.loads((outdir / "execution_plan.resolved.json").read_text(encoding="utf-8"))
    planned = jsonlib.loads((outdir / "execution_plan.json").read_text(encoding="utf-8"))
    assert [s["step_id"] for s in resolved["steps"]] == [s["step_id"] for s in planned["steps"]]


def test_shared_dry_run_rejects_outdir_that_is_file(tmp_path: Path) -> None:
    """An outdir path that exists as a file must fail with a clear error."""
    import pytest

    from abi.schemas import ABIError

    outdir = tmp_path / "out"
    outdir.write_text("not a directory\n", encoding="utf-8")

    coordinator, prepared = _prepare(tmp_path, skipped=[], outdir=outdir)

    with pytest.raises(ABIError, match="not a directory"):
        coordinator.dry_run(prepared)
