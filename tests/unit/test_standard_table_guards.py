"""Unit tests for the standard-table empty-output guards.

Defense-in-depth for runs where a declared standard table stays header-only
(e.g. a real rnaseq run whose parser source file lived at
``04_differential_expression/count_matrix.tsv`` instead of the expected
``<output_dir>/count_matrix.tsv``).  Every guard is non-fatal by design:
parsers log a warning, the executor records a per-step reason plus a
run-level warnings list, and the result writer surfaces ``empty_tables``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

from abi.executor import GenericABIExecutor
from abi.plugins.rnaseq_expression import _parse_count_matrix
from abi.provenance import RunLogger
from abi.results import ABIResultWriter
from abi.schemas import ExecutionPlan, PlanStep, SampleContext, SampleInput
from abi.tables import StandardTableManager

_SAMPLE = SampleInput(sample_id="S1", platform="assembly", assembly="S1.fa")
_CONTEXT = SampleContext([_SAMPLE], True, False, True, False)

# ── Parser-level guards (abi.plugins.rnaseq_expression._parse_count_matrix) ──


def test_parse_count_matrix_missing_source_warns_and_returns_empty(tmp_path: Path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="abi.plugins.rnaseq_expression"):
        rows = _parse_count_matrix(tmp_path / "missing")

    assert rows == []
    assert any("no source file" in record.message for record in caplog.records)


def test_parse_count_matrix_malformed_header_warns_and_returns_empty(
    tmp_path: Path, caplog
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "count_matrix.tsv").write_text("gene_id\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="abi.plugins.rnaseq_expression"):
        rows = _parse_count_matrix(output_dir)

    assert rows == []
    assert any("malformed header" in record.message for record in caplog.records)


def test_parse_count_matrix_long_format_header_warns_about_format_confusion(
    tmp_path: Path, caplog
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "count_matrix.tsv").write_text(
        "gene_id\tsample_id\tcount\ng1\tS1\t10\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="abi.plugins.rnaseq_expression"):
        rows = _parse_count_matrix(output_dir)

    assert rows == []
    assert any("long-format columns" in record.message for record in caplog.records)


def test_parse_count_matrix_zero_data_rows_warns_and_returns_empty(tmp_path: Path, caplog) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "count_matrix.tsv").write_text("gene_id\tS1\tS2\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="abi.plugins.rnaseq_expression"):
        rows = _parse_count_matrix(output_dir)

    assert rows == []
    assert any("zero data rows" in record.message for record in caplog.records)


# ── Executor-level escalation (abi.executor run summary warnings) ───────────


class _EmptyParsePlugin:
    """Minimal parse_outputs seam: declares tables but parses zero rows."""

    def parse_outputs(self, tool_id: str, output_dir: str, sample_id: str):
        return {}

    def standard_tables_for_tool(self, tool_id: str) -> list[str]:
        return ["count_matrix"] if tool_id == "tool" else []


class _Registry:
    def has(self, tool_id: str) -> bool:
        return tool_id == "tool"

    def get(self, tool_id: str):
        return {"output_dir_policy": "create"}

    def create(self, tool_id: str, *, mock_tools: bool = False):
        return _Skill()

    def list_tools(self) -> list:
        return []

    def check_tools(self, *, mock_tools: bool = False, config=None) -> list:
        return []


class _Skill:
    def build_command(self, params):
        return ["tool", "--output", str(params.get("output_dir", ""))]

    def run(self, params, *, dry_run: bool):
        return SimpleNamespace(return_code=0, status="success", outputs={})


def _step(**overrides) -> PlanStep:
    values = {
        "step_id": "build_count_matrix",
        "step_name": "Build count matrix",
        "tool_id": "tool",
        "category": "quantification",
        "sample_id": None,
    }
    values.update(overrides)
    return PlanStep(**values)


def test_executor_records_no_standard_rows_warning_in_run_summary(tmp_path: Path) -> None:
    outdir = tmp_path / "out"
    plugin = _EmptyParsePlugin()
    executor = GenericABIExecutor(
        _Registry(),
        RunLogger(tmp_path / "logs"),
        table_manager=StandardTableManager(
            {"count_matrix": ["gene_id", "sample_id", "count", "tool", "source_file"]}
        ),
        parse_outputs=plugin.parse_outputs,
        enforce_contracts=False,
    )
    plan = ExecutionPlan(
        project_name="guards",
        mode="auto",
        threads=1,
        outdir=str(outdir),
        log_dir=str(tmp_path / "logs"),
        samples=[_SAMPLE],
        sample_context=_CONTEXT,
        selected_tools=["tool"],
        steps=[_step(outputs={"output_dir": str(outdir / "count_matrix")})],
    )

    outputs = executor.run(plan, {"outdir": str(outdir)})

    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    warnings = summary["warnings"]
    assert len(warnings) == 1
    assert warnings[0]["step_id"] == "build_count_matrix"
    assert warnings[0]["tool_id"] == "tool"
    assert "no standard rows parsed" in warnings[0]["reason"]
    # The same warning is also visible in the commands.tsv reason column.
    commands = outputs["commands"].read_text(encoding="utf-8")
    assert "no standard rows parsed" in commands


# ── Results-level surface (abi.results ABIResultWriter empty_tables) ────────


class _WriterPlugin:
    report_title = "Test Report"

    def table_schemas(self):
        return {
            "count_matrix": ["gene_id", "sample_id", "count", "tool", "source_file"],
            "gene_stats": ["gene_id", "base_mean"],
        }


class _WriterRegistry:
    def list_tools(self) -> list:
        return []

    def check_tools(self, *, mock_tools: bool = False, config=None) -> list:
        return []


def test_result_writer_lists_header_only_tables_under_empty_tables(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    tables_dir = result_dir / "tables"
    tables_dir.mkdir(parents=True)
    # Pre-create one populated table; ensure_tables() is idempotent and keeps it.
    (tables_dir / "gene_stats.tsv").write_text(
        "gene_id\tbase_mean\ng1\t42\n",
        encoding="utf-8",
    )
    plan = ExecutionPlan(
        project_name="guards",
        mode="auto",
        threads=1,
        outdir=str(result_dir),
        log_dir=str(tmp_path / "logs"),
        samples=[_SAMPLE],
        sample_context=_CONTEXT,
        selected_tools=[],
        steps=[],
    )
    writer = ABIResultWriter(_WriterPlugin(), _WriterRegistry())

    writer.write(
        plan=plan,
        config={"outdir": str(result_dir)},
        command_rows=[],
        status="success",
    )

    summary = json.loads(
        (result_dir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["warnings"]["empty_tables"] == ["count_matrix"]
