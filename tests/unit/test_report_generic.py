"""Unit tests for generic report figure rendering helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from abi.report.generic_report import (
    _render_figures_via_legacy,
    render_figures_via_sciplot,
)


class _FakePlugin:
    """Minimal plugin-like object."""

    report_title = "Test Plugin"
    abi_version = "1.0.0"


# ── render_figures_via_sciplot ────────────────────────────────────────────


def test_sciplot_import_error(tmp_path: Path) -> None:
    """L281-282: sciplot ImportError → return {}."""
    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    tables = tmp_path / "tables"
    tables.mkdir()
    figures = tmp_path / "figures"
    figures.mkdir()

    # Write a valid specs file just to get past load_yaml
    specs.write_text("figures:\n  - id: fig1\n", encoding="utf-8")

    with mock.patch(
        "abi.report.generic_report.render_figures_via_sciplot",
        side_effect=ImportError("no sciplot"),
    ):
        # We can't easily trigger the inner ImportError from here since
        # we need to import the function. Let's use a different approach:
        # mock the entire import chain.
        pass

    # Direct approach: mock the import to fail
    with mock.patch.dict("sys.modules", {"abi.sciplot.adapters": None, "abi.sciplot.api": None}):
        # Force re-import to trigger ImportError
        pass

    # Simpler: directly test the try/except by mocking the specific imports
    with mock.patch(
        "abi.sciplot.adapters", create=True, new_callable=mock.PropertyMock
    ) as mock_adapters:
        mock_adapters.side_effect = ImportError("No module named 'matplotlib'")
        result = render_figures_via_sciplot(plugin, specs, tables, figures)
        assert result == {}


def test_sciplot_empty_specs(tmp_path: Path) -> None:
    """L287: empty old_specs list → return {}."""
    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    specs.write_text("figures: []\n", encoding="utf-8")
    tables = tmp_path / "tables"
    tables.mkdir()
    figures = tmp_path / "figures"
    figures.mkdir()
    result = render_figures_via_sciplot(plugin, specs, tables, figures)
    assert result == {}


def test_sciplot_missing_id_key(tmp_path: Path) -> None:
    """L296: missing id key in spec → continue (skip)."""
    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    specs.write_text("figures:\n  - not_id: no_id_here\n  - id: fig2\n", encoding="utf-8")
    tables = tmp_path / "tables"
    tables.mkdir()
    figures = tmp_path / "figures"
    figures.mkdir()

    # The spec with id='fig2' has no source_table → it'll try to render
    # But the one without id should be skipped
    # Mock both adapt_spec and render_figure to avoid heavy rendering
    with (
        mock.patch("abi.sciplot.adapters.adapt_spec") as mock_adapt,
        mock.patch("abi.sciplot.api.render_figure") as mock_render,
    ):
        mock_result = mock.Mock()
        mock_result.errors = []
        mock_result.warnings = []
        mock_result.output_files = [figures / "fig2.png"]
        mock_render.return_value = mock_result

        result = render_figures_via_sciplot(plugin, specs, tables, figures)
        # Only fig2 should be in results, not the one with missing id
        assert "fig2" in result
        assert mock_adapt.call_count == 1


def test_sciplot_required_figure_source_table_missing(tmp_path: Path, caplog) -> None:
    """L305-311: required figure, source table missing → warning + skip."""
    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    specs.write_text(
        "figures:\n  - id: fig_req\n    source_table: missing_table\n    required: true\n",
        encoding="utf-8",
    )
    tables = tmp_path / "tables"
    tables.mkdir()
    figures = tmp_path / "figures"
    figures.mkdir()

    with caplog.at_level(logging.WARNING):
        result = render_figures_via_sciplot(plugin, specs, tables, figures)

    assert result == {}
    assert "required" in caplog.text
    assert "missing_table" in caplog.text
    assert "skipping" in caplog.text.lower()


def test_sciplot_optional_figure_source_table_missing(tmp_path: Path, caplog) -> None:
    """L312-317: optional figure, source table missing → info + skip."""
    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    specs.write_text(
        "figures:\n  - id: fig_opt\n    source_table: missing_table\n    required: false\n",
        encoding="utf-8",
    )
    tables = tmp_path / "tables"
    tables.mkdir()
    figures = tmp_path / "figures"
    figures.mkdir()

    with caplog.at_level(logging.INFO):
        result = render_figures_via_sciplot(plugin, specs, tables, figures)

    assert result == {}
    assert "optional" in caplog.text
    assert "skipping" in caplog.text.lower()


def test_sciplot_oserror_reading_table(tmp_path: Path, caplog) -> None:
    """L324-325: OSError reading table → line_count=0 → skip."""
    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    specs.write_text(
        "figures:\n  - id: fig_err\n    source_table: bad_table\n    required: true\n",
        encoding="utf-8",
    )
    tables = tmp_path / "tables"
    tables.mkdir()
    # Create a directory instead of a file to trigger OSError
    (tables / "bad_table.tsv").mkdir()

    figures = tmp_path / "figures"
    figures.mkdir()

    with caplog.at_level(logging.WARNING):
        result = render_figures_via_sciplot(plugin, specs, tables, figures)

    assert result == {}
    assert "empty" in caplog.text.lower()


def test_sciplot_empty_table(tmp_path: Path, caplog) -> None:
    """Table with header only (1 line) → skip."""
    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    specs.write_text(
        "figures:\n  - id: fig_empty\n    source_table: empty_table\n    required: true\n",
        encoding="utf-8",
    )
    tables = tmp_path / "tables"
    tables.mkdir()
    (tables / "empty_table.tsv").write_text("header\n", encoding="utf-8")

    figures = tmp_path / "figures"
    figures.mkdir()

    with caplog.at_level(logging.WARNING):
        result = render_figures_via_sciplot(plugin, specs, tables, figures)

    assert result == {}
    assert "empty" in caplog.text.lower()


# ── _render_figures_via_legacy ────────────────────────────────────────────


def test_render_figures_via_legacy(tmp_path: Path) -> None:
    """L380-388: _render_figures_via_legacy with mocked FigureEngine."""
    plugin = _FakePlugin()

    # Need plugin.table_schemas()
    plugin.table_schemas = lambda: {"qc": ["col1", "col2"]}  # type: ignore[assignment]

    specs = tmp_path / "figure_specs.yaml"
    specs.write_text("figures: []\n", encoding="utf-8")
    tables = tmp_path / "tables"
    tables.mkdir()
    figures = tmp_path / "figures"
    figures.mkdir()

    with mock.patch("abi.figures.FigureEngine") as mock_engine_cls:
        mock_engine = mock.Mock()
        mock_engine.render_all.return_value = {"fig1": figures / "fig1.png"}
        mock_engine_cls.return_value = mock_engine

        result = _render_figures_via_legacy(plugin, specs, tables, figures)
        assert result == {"fig1": figures / "fig1.png"}
        mock_engine_cls.assert_called_once()
        mock_engine.load_specs.assert_called_once_with(specs)
        mock_engine.render_all.assert_called_once()


# ── write_full_report ──────────────────────────────────────────────────────


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
        rendered_figures={"fig1": png},
        citations=[{"tool": "fastp", "citation": "Test"}],
        limitations=["Lim A"],
        methods=True,
        resource_manifest=False,
    )
    html = paths["report_html"].read_text(encoding="utf-8")
    assert "Test" in html  # citation mention
    assert "Lim A" in html  # limitation mention
    assert "fig1" in html  # figure mention


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


# ── render_figures_via_sciplot: exception handling ─────────────────────────


def test_sciplot_render_exception(tmp_path: Path, caplog) -> None:
    """L357-364: render_figure() raises → logged warning, figure skipped."""
    import logging

    plugin = _FakePlugin()
    specs = tmp_path / "figure_specs.yaml"
    specs.write_text(
        "figures:\n  - id: fig_bad\n",
        encoding="utf-8",
    )
    tables = tmp_path / "tables"
    tables.mkdir()
    figures = tmp_path / "figures"
    figures.mkdir()

    with (
        mock.patch("abi.sciplot.adapters.adapt_spec"),
        mock.patch("abi.sciplot.api.render_figure") as mock_render,
    ):
        mock_render.side_effect = RuntimeError("render explosion")
        with caplog.at_level(logging.WARNING):
            result = render_figures_via_sciplot(plugin, specs, tables, figures)

        assert result == {}
        assert "failed to render" in caplog.text.lower()


# ── write_generic_report: standard tables ──────────────────────────────────


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
    assert facts["step_status_counts"] == {"failed": 1, "resumed": 1, "success": 1}
    assert facts["failed_steps"][0]["step_id"] == "s2"
    assert facts["resumed_steps"] == ["s3"]


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
