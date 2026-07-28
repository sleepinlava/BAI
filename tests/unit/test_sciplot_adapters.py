from __future__ import annotations

import json

from abi.sciplot.adapters import adapt_spec
from abi.sciplot.provenance import write_provenance


def test_adapter_separates_categorical_palettes_from_matplotlib_colormaps(tmp_path):
    categorical = adapt_spec(
        {
            "id": "groups",
            "type": "scatter",
            "source_table": "metrics",
            "x": "x",
            "y": "y",
            "color": "group",
            "colormap": "viridis",
        },
        tmp_path,
        tmp_path / "figures",
    )
    diverging = adapt_spec(
        {
            "id": "expression",
            "type": "heatmap",
            "source_table": "expression",
            "x": "gene_id",
            "colormap": "RdBu_r",
        },
        tmp_path,
        tmp_path / "figures",
    )

    assert categorical.style.palette == "colorblind_safe_8"
    assert categorical.labels.legend_title == "group"
    assert diverging.style.palette == "coolwarm"


def test_figure_provenance_records_input_role_and_workflow(tmp_path):
    table = tmp_path / "metrics.tsv"
    table.write_text("x\ty\n1\t2\n", encoding="utf-8")
    spec = adapt_spec(
        {
            "id": "metrics",
            "type": "scatter",
            "source_table": "metrics",
            "x": "x",
            "y": "y",
        },
        tmp_path,
        tmp_path / "figures",
        plugin_name="Demo workflow",
    )

    path = write_provenance(spec, tmp_path / "provenance")
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["input_data_role"] == "metrics"
    assert record["workflow_name"] == "Demo workflow"


def test_figure_provenance_binds_source_run_and_standard_table(tmp_path):
    table = tmp_path / "metrics.tsv"
    table.write_text("x\ty\n1\t2\n", encoding="utf-8")
    spec = adapt_spec(
        {
            "id": "metrics",
            "type": "scatter",
            "source_table": "metrics",
            "x": "x",
            "y": "y",
        },
        tmp_path,
        tmp_path / "figures",
    )
    spec.provenance.source_run_id = "run-123"
    spec.provenance.source_standard_table = "tables/differential_expression.tsv"
    spec.provenance.source_standard_table_sha256 = "a" * 64

    path = write_provenance(spec, tmp_path / "provenance")
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["source_run_id"] == "run-123"
    assert record["source_standard_table"] == "tables/differential_expression.tsv"
    assert record["source_standard_table_sha256"] == "a" * 64
