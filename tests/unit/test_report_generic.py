"""Unit tests for generic report figure rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


class _FakePlugin:
    """Minimal plugin-like object."""

    report_title = "Test Plugin"
    abi_version = "1.0.0"


def test_write_full_report_basic(tmp_path: Path) -> None:
    """write_full_report produces report.md, report.html, methods.md."""
    from abi.report.generic_report import write_full_report

    result_dir = tmp_path
    (result_dir / "tables").mkdir()
    (result_dir / "provenance").mkdir()
    (result_dir / "provenance" / "tool_versions.tsv").write_text(
        "tool_id\tversion\n",
        encoding="utf-8",
    )
    (result_dir / "provenance" / "commands.tsv").write_text(
        "step_id\tcommand\n",
        encoding="utf-8",
    )

    class FakePlan:
        def to_dict(self):
            return {
                "analysis_type": "test",
                "project_name": "full-report",
                "steps": [],
            }

    paths = write_full_report(
        FakePlan(),
        result_dir,
        table_summary={},
        title="Test Report",
        methods=True,
        resource_manifest=False,
    )
    assert "report" in paths
    assert "report_html" in paths
    assert "methods" in paths
    assert paths["report"].exists()
    assert paths["report_html"].exists()
    assert paths["methods"].exists()


def test_write_full_report_no_methods(tmp_path: Path) -> None:
    """write_full_report with methods=False → no methods.md."""
    from abi.report.generic_report import write_full_report

    result_dir = tmp_path
    (result_dir / "tables").mkdir()
    (result_dir / "provenance").mkdir()

    class FakePlan:
        def to_dict(self):
            return {
                "analysis_type": "test",
                "project_name": "no-methods",
                "steps": [],
            }

    paths = write_full_report(
        FakePlan(),
        result_dir,
        table_summary={},
        methods=False,
        resource_manifest=False,
    )
    assert "methods" not in paths


def test_write_full_report_with_all_options(tmp_path: Path) -> None:
    """write_full_report with citations, limitations, and figures."""
    from abi.report.generic_report import write_full_report

    result_dir = tmp_path
    (result_dir / "tables").mkdir()
    (result_dir / "provenance").mkdir()
    (result_dir / "provenance" / "tool_versions.tsv").write_text(
        "tool_id\tversion\n",
        encoding="utf-8",
    )
    (result_dir / "provenance" / "commands.tsv").write_text(
        "step_id\tcommand\n",
        encoding="utf-8",
    )
    figs_dir = result_dir / "figures"
    figs_dir.mkdir()
    png = figs_dir / "test.png"
    png.write_text("fake-png")

    class FakePlan:
        def to_dict(self):
            return {
                "analysis_type": "test",
                "project_name": "all-options",
                "steps": [],
            }

    paths = write_full_report(
        FakePlan(),
        result_dir,
        table_summary={},
        title="Full Report",
        citations=[{"tool": "fastp", "citation": "Test"}],
        limitations=["Lim A"],
        methods=True,
        resource_manifest=False,
    )
    html = paths["report_html"].read_text(encoding="utf-8")
    assert "Test" in html  # citation mention
    assert "Lim A" in html  # limitation mention


def test_write_full_report_passes_generated_resource_manifest_to_methods(tmp_path: Path) -> None:
    """Configured databases are rendered in methods during the same report call."""
    from abi.report.generic_report import write_full_report

    (tmp_path / "tables").mkdir()
    provenance = tmp_path / "provenance"
    provenance.mkdir()
    (provenance / "tool_versions.tsv").write_text("tool_id\tversion\n", encoding="utf-8")
    (provenance / "commands.tsv").write_text("step_id\tcommand\n", encoding="utf-8")

    paths = write_full_report(
        {"analysis_type": "test", "project_name": "configured-resources", "steps": []},
        tmp_path,
        table_summary={},
        config={"resources": {"host_db": "/ref/host", "kraken2_db": "/ref/kraken2"}},
    )

    methods = paths["methods"].read_text(encoding="utf-8")
    assert "| host_db | not_captured | `/ref/host` |" in methods
    assert "| kraken2_db | not_captured | `/ref/kraken2` |" in methods
    assert paths["resource_manifest"].exists()


def test_write_full_report_reuses_existing_resource_manifest(tmp_path: Path) -> None:
    """Report regeneration without config still renders the persisted database manifest."""
    from abi.report.generic_report import write_full_report

    (tmp_path / "tables").mkdir()
    provenance = tmp_path / "provenance"
    provenance.mkdir()
    (provenance / "tool_versions.tsv").write_text("tool_id\tversion\n", encoding="utf-8")
    (provenance / "commands.tsv").write_text("step_id\tcommand\n", encoding="utf-8")
    manifest_path = provenance / "resource_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "analysis_type": "test",
                "resources": [{"id": "host_db", "path": "/ref/host", "version": ""}],
            }
        ),
        encoding="utf-8",
    )

    paths = write_full_report(
        {"analysis_type": "test", "project_name": "regenerated-report", "steps": []},
        tmp_path,
        table_summary={},
    )

    methods = paths["methods"].read_text(encoding="utf-8")
    assert "| host_db | not_captured | `/ref/host` |" in methods
    assert paths["resource_manifest"] == manifest_path


def test_write_generic_report_with_tables(tmp_path: Path) -> None:
    """write_generic_report with multiple tables in summary."""
    from abi.report.generic_report import write_generic_report

    result_dir = tmp_path

    class FakePlan:
        def to_dict(self):
            return {
                "analysis_type": "test",
                "project_name": "multi-tables",
                "selected_tools": ["tool1", "tool2"],
                "steps": [{"step_id": "s1"}],
            }

    paths = write_generic_report(
        FakePlan(),
        result_dir,
        table_summary={
            "samples": {"rows": 5, "path": "tables/samples.tsv"},
            "qc": {"rows": 100, "path": "tables/qc.tsv"},
        },
        title="Multi Table Report",
    )
    assert paths["report"].exists()
    assert paths["report_html"].exists()
    md = paths["report"].read_text(encoding="utf-8")
    assert "samples.tsv" in md
    assert "qc.tsv" in md
    assert "tool1" in md


def test_generic_report_records_execution_facts(tmp_path):
    """WP5: failed calls and reused steps are explicit; not just plan tables."""
    from abi.report.generic_report import build_run_facts, write_generic_report

    plan = SimpleNamespace(
        to_dict=lambda: {
            "project_name": "facts",
            "analysis_type": "test",
            "selected_tools": ["tool"],
            "steps": [{"step_id": "s1"}, {"step_id": "s2"}],
        }
    )
    command_rows = [
        {"step_id": "s1", "tool_id": "tool", "status": "success", "reason": ""},
        {
            "step_id": "s2",
            "tool_id": "tool",
            "status": "failed",
            "reason": "resume reuse rejected: output checksum mismatch",
        },
        {"step_id": "s3", "tool_id": "tool", "status": "resumed", "reason": ""},
        {"step_id": "s4", "tool_id": "tool", "status": "dry_run", "reason": ""},
        {"step_id": "s5", "tool_id": "tool", "status": "skipped", "reason": "planned"},
    ]
    run_summary = {
        "status": "failed",
        "run_id": "run-1",
        "plan_id": "sha256:abc",
        "resumes_run_id": "run-0",
        "previous_run_archive": "previous_runs/run-0",
    }

    outputs = write_generic_report(
        plan,
        tmp_path,
        table_summary={"summary": {"rows": 1, "path": "tables/summary.tsv"}},
        run_facts=build_run_facts(command_rows, run_summary),
    )

    md = outputs["report"].read_text(encoding="utf-8")
    assert "## Execution Facts" in md
    assert "Failed calls:" in md
    assert "resume reuse rejected" in md
    assert "Reused steps (validated resume):** `s3`" in md
    assert "resumes run `run-0`" in md
    assert "prior evidence archived at `previous_runs/run-0`" in md
    assert "plan identity `sha256:abc`" in md

    summary = json.loads((tmp_path / "report" / "report_summary.json").read_text())
    facts = summary["execution_facts"]
    assert facts["step_status_counts"] == {
        "dry_run": 1,
        "failed": 1,
        "resumed": 1,
        "skipped": 1,
        "success": 1,
    }
    assert facts["failed_steps"][0]["step_id"] == "s2"
    assert facts["resumed_steps"] == ["s3"]
    assert len(facts["actual_calls"]) == 3
    assert [call["step_id"] for call in facts["command_records"]] == [
        "s1",
        "s2",
        "s3",
        "s4",
        "s5",
    ]
    assert [call["step_id"] for call in facts["actual_calls"]] == ["s1", "s2", "s3"]
    assert facts["actual_calls"][0]["command"] == ""
    assert "Actual calls (excluding dry-run and skipped steps):" in md
    assert "s1" in md


def test_generic_report_states_when_facts_are_absent(tmp_path):
    """WP5: a report without command facts says so instead of implying them."""
    from abi.report.generic_report import write_generic_report

    plan = SimpleNamespace(
        to_dict=lambda: {"project_name": "nofacts", "analysis_type": "t", "steps": []}
    )
    outputs = write_generic_report(
        plan,
        tmp_path,
        table_summary={},
    )
    md = outputs["report"].read_text(encoding="utf-8")
    assert "Execution Facts" in md
    assert "not provided" in md
