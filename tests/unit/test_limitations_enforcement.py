"""Enforcement tests for mandatory limitation disclosure.

Covers the Phase 1 contract: every built-in plugin ships a non-empty
``limitations.yaml``, the contract linter flags missing/empty/unparseable
declarations, and generated reports (Markdown/HTML/JSON) always contain
limitations content — falling back to an explicit sentence rather than
silently omitting the section.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abi.config import PLUGIN_ROOT
from abi.contracts.lint import lint_limitations, run_contract_lint
from abi.report.generic_report import write_generic_report
from abi.report.html import write_html_report
from abi.report.limitations import (
    FALLBACK_LIMITATION,
    format_limitations_html,
    format_limitations_markdown,
    load_limitations,
)
from abi.report.methods import write_methods

BUILTIN_PLUGIN_IDS = [
    "amplicon_16s",
    "easymetagenome",
    "metagenomic_plasmid",
    "metatranscriptomics",
    "rnaseq_expression",
    "viral_viwrap",
    "wgs_bacteria",
]


class FakePlan:
    def to_dict(self):
        return {
            "analysis_type": "test",
            "project_name": "limitations-enforcement",
            "selected_tools": ["fastp"],
            "steps": [],
        }


# ── (a) every built-in plugin ships a non-empty limitations.yaml ──────────


@pytest.mark.parametrize("plugin_id", BUILTIN_PLUGIN_IDS)
def test_builtin_plugin_ships_non_empty_limitations(plugin_id: str) -> None:
    plugin_root = PLUGIN_ROOT / plugin_id
    path = plugin_root / "limitations.yaml"
    assert path.exists(), f"{plugin_id} is missing limitations.yaml"
    entries = load_limitations(path)
    assert entries, f"{plugin_id} limitations.yaml declares no limitations"
    assert all(entry.strip() for entry in entries)
    assert lint_limitations(plugin_root) == []


# ── (b) lint flags missing / empty / unparseable declarations ─────────────


def test_lint_flags_missing_limitations(tmp_path: Path) -> None:
    findings = lint_limitations(tmp_path)
    assert any(f.severity == "error" and f.check == "missing_limitations" for f in findings)


def test_lint_flags_empty_limitations(tmp_path: Path) -> None:
    (tmp_path / "limitations.yaml").write_text("limitations: []\n", encoding="utf-8")
    findings = lint_limitations(tmp_path)
    assert any(f.severity == "error" and f.check == "empty_limitations" for f in findings)


def test_lint_flags_blank_only_limitations(tmp_path: Path) -> None:
    (tmp_path / "limitations.yaml").write_text('limitations:\n  - " "\n', encoding="utf-8")
    findings = lint_limitations(tmp_path)
    assert any(f.severity == "error" and f.check == "empty_limitations" for f in findings)


def test_lint_flags_unparseable_limitations(tmp_path: Path) -> None:
    (tmp_path / "limitations.yaml").write_text("limitations: [unclosed\n", encoding="utf-8")
    findings = lint_limitations(tmp_path)
    assert any(f.severity == "error" and f.check == "invalid_limitations" for f in findings)


def test_lint_flags_non_mapping_limitations(tmp_path: Path) -> None:
    (tmp_path / "limitations.yaml").write_text("- just a list\n", encoding="utf-8")
    findings = lint_limitations(tmp_path)
    assert any(f.severity == "error" and f.check == "empty_limitations" for f in findings)


def test_run_contract_lint_includes_limitations_findings(tmp_path: Path) -> None:
    dag = {"nodes": [{"id": "A", "depends_on": []}]}
    result = run_contract_lint(dag, plugin_root=tmp_path)
    assert result["passed"] is False
    assert any(f["check"] == "missing_limitations" for f in result["findings"])


def test_run_contract_lint_passes_with_limitations(tmp_path: Path) -> None:
    (tmp_path / "limitations.yaml").write_text(
        "limitations:\n  - Declared limitation.\n", encoding="utf-8"
    )
    dag = {"nodes": [{"id": "A", "depends_on": []}]}
    result = run_contract_lint(dag, plugin_root=tmp_path)
    assert result["passed"] is True


# ── (c) generated reports contain limitations content ─────────────────────


def test_generic_report_summary_json_contains_limitations(tmp_path: Path) -> None:
    write_generic_report(
        FakePlan(),
        tmp_path,
        table_summary={},
        limitations=["Declared limitation A"],
    )
    summary = json.loads((tmp_path / "report" / "report_summary.json").read_text("utf-8"))
    assert summary["limitations"] == ["Declared limitation A"]


def test_generic_report_markdown_and_html_contain_limitations(tmp_path: Path) -> None:
    write_generic_report(
        FakePlan(),
        tmp_path,
        table_summary={},
        limitations=["Declared limitation A"],
    )
    md = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    html = (tmp_path / "report" / "report.html").read_text(encoding="utf-8")
    assert "## Known Limitations" in md
    assert "Declared limitation A" in md
    assert "Known Limitations" in html
    assert "Declared limitation A" in html


def test_write_html_report_contains_declared_limitations(tmp_path: Path) -> None:
    out = write_html_report(
        tmp_path,
        plan=FakePlan(),
        table_summary={},
        limitations_yaml=["Declared limitation B"],
    )
    content = out.read_text(encoding="utf-8")
    assert "<h2>Known Limitations</h2>" in content
    assert "<li>Declared limitation B</li>" in content


def test_write_methods_contains_declared_limitations(tmp_path: Path) -> None:
    _prepare_provenance(tmp_path)
    out = write_methods(tmp_path, plan=FakePlan(), limitations=["Declared limitation C"])
    content = out.read_text(encoding="utf-8")
    assert "## Known Limitations" in content
    assert "1. Declared limitation C" in content


def test_plasmid_markdown_report_contains_declared_limitations(tmp_path: Path) -> None:
    pytest.importorskip("abi.plugins.metagenomic_plasmid")
    from abi.plugins.metagenomic_plasmid._engine.report.markdown import write_markdown_report
    from abi.plugins.metagenomic_plasmid._engine.standard_tables import ensure_standard_tables
    from abi.schemas import ExecutionPlan, SampleContext, SampleInput

    tables_dir = tmp_path / "tables"
    ensure_standard_tables(tables_dir)
    sample = SampleInput(sample_id="S1", platform="illumina")
    plan = ExecutionPlan(
        project_name="test",
        mode="auto",
        threads=1,
        outdir=str(tmp_path / "results"),
        log_dir=str(tmp_path / "logs"),
        samples=[sample],
        sample_context=SampleContext(
            samples=[sample],
            multi_sample=False,
            has_groups=False,
            enable_sample_analysis=False,
            enable_differential_abundance=False,
        ),
        selected_tools=["genomad"],
        steps=[],
    )
    report_path = write_markdown_report(plan, tmp_path / "report", tables_dir=tables_dir)
    content = report_path.read_text(encoding="utf-8")
    assert "## Known Limitations" in content
    declared = load_limitations(PLUGIN_ROOT / "metagenomic_plasmid" / "limitations.yaml")
    assert declared and declared[0] in content


def test_plasmid_html_report_contains_declared_limitations(tmp_path: Path) -> None:
    pytest.importorskip("abi.plugins.metagenomic_plasmid")
    from abi.plugins.metagenomic_plasmid._engine.report.html import (
        write_html_report as write_plasmid_html_report,
    )
    from abi.plugins.metagenomic_plasmid._engine.standard_tables import ensure_standard_tables
    from abi.schemas import ExecutionPlan, SampleContext, SampleInput

    tables_dir = tmp_path / "tables"
    ensure_standard_tables(tables_dir)
    sample = SampleInput(sample_id="S1", platform="illumina")
    plan = ExecutionPlan(
        project_name="test",
        mode="auto",
        threads=1,
        outdir=str(tmp_path / "results"),
        log_dir=str(tmp_path / "logs"),
        samples=[sample],
        sample_context=SampleContext(
            samples=[sample],
            multi_sample=False,
            has_groups=False,
            enable_sample_analysis=False,
            enable_differential_abundance=False,
        ),
        selected_tools=["genomad"],
        steps=[],
    )
    report_path = write_plasmid_html_report(plan, tmp_path / "report", tables_dir=tables_dir)
    content = report_path.read_text(encoding="utf-8")
    assert "<h2>Known Limitations</h2>" in content
    declared = load_limitations(PLUGIN_ROOT / "metagenomic_plasmid" / "limitations.yaml")
    assert declared and declared[0] in content


# ── (d) the empty-list fallback appears rather than omission ──────────────


def test_format_markdown_fallback_when_empty() -> None:
    text = format_limitations_markdown([])
    assert "## Known Limitations" in text
    assert FALLBACK_LIMITATION in text


def test_format_html_fallback_when_empty() -> None:
    text = format_limitations_html([])
    assert "<h2>Known Limitations</h2>" in text
    assert FALLBACK_LIMITATION in text


def test_write_html_report_fallback_when_no_limitations(tmp_path: Path) -> None:
    out = write_html_report(tmp_path, plan=FakePlan(), table_summary={})
    content = out.read_text(encoding="utf-8")
    assert "<h2>Known Limitations</h2>" in content
    assert FALLBACK_LIMITATION in content


def test_write_methods_fallback_when_no_limitations(tmp_path: Path) -> None:
    _prepare_provenance(tmp_path)
    out = write_methods(tmp_path, plan=FakePlan())
    content = out.read_text(encoding="utf-8")
    assert "## Known Limitations" in content
    assert FALLBACK_LIMITATION in content


def test_generic_report_fallback_when_no_limitations(tmp_path: Path) -> None:
    write_generic_report(FakePlan(), tmp_path, table_summary={})
    md = (tmp_path / "report" / "report.md").read_text(encoding="utf-8")
    html = (tmp_path / "report" / "report.html").read_text(encoding="utf-8")
    summary = json.loads((tmp_path / "report" / "report_summary.json").read_text("utf-8"))
    assert "## Known Limitations" in md
    assert FALLBACK_LIMITATION in md
    assert FALLBACK_LIMITATION in html
    assert summary["limitations"] == []


# ── helpers ───────────────────────────────────────────────────────────────


def _prepare_provenance(result_dir: Path) -> None:
    """Write the minimal provenance files write_methods expects."""
    prov_dir = result_dir / "provenance"
    prov_dir.mkdir(parents=True, exist_ok=True)
    (prov_dir / "tool_versions.tsv").write_text(
        "tool_id\tversion\nfastp\t0.23.4\n", encoding="utf-8"
    )
    (prov_dir / "commands.tsv").write_text(
        "step_id\tcommand\nS1_qc\tfastp -i in.fq\n", encoding="utf-8"
    )
