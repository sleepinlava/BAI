import csv
from pathlib import Path

import pytest

from scripts import create_real_data_case_study_figures as figure_builder


def test_create_figures_rejects_missing_scapp_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Missing frozen SCAPP evidence table"):
        figure_builder.create_figures(tmp_path / "missing.tsv")


def test_create_figures_excludes_benchmark_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "scapp.tsv"
    fields = [
        "plasmid_id",
        "length_bp",
        "log10_length_bp",
        "abundance_coverage",
        "log10_abundance_coverage",
        "is_circular",
        "amr_hit_count",
        "predicted_mobility",
    ]
    rows = ["\t".join(fields)]
    for index in range(157):
        rows.append(
            "\t".join(
                [
                    f"p{index}",
                    "1000",
                    "3.0",
                    "10.0",
                    "1.0",
                    "False",
                    "0",
                    "non-mobilizable",
                ]
            )
        )
    source.write_text("\n".join(rows) + "\n")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(figure_builder, "FIGURE_DIR", tmp_path / "figures")
    monkeypatch.setattr(figure_builder, "DATA_DIR", data_dir)
    for name in ("airway_metrics.tsv", "wgs_metrics.tsv", "wgs_snp_pairwise_distances.tsv"):
        original = Path(__file__).resolve().parents[2] / "docs/paper_examples" / name
        (data_dir / name).write_bytes(original.read_bytes())
    result = figure_builder.create_figures(source)
    assert result["benchmark_outcomes_used"] is False
    assert len(result["figures"]) == 3
    assert all(figure["source_run_id"] for figure in result["figures"])
    assert all(len(figure["source_standard_table_sha256"]) == 64 for figure in result["figures"])
    derived = (data_dir / "scapp_biological_evidence.tsv").read_text()
    assert "reference_matched" not in derived


def test_canonical_metrics_exclude_historical_benchmark_outcomes() -> None:
    path = Path(__file__).resolve().parents[2] / "metrics.tsv"
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    benchmark_rows = [row for row in rows if row["evidence_track"] == "agent_operability"]
    assert benchmark_rows
    assert all(row["status"] == "pending_new_run" for row in benchmark_rows)
    assert all(not row["estimate"] for row in benchmark_rows)


def test_biological_metrics_bind_source_run_and_standard_table() -> None:
    path = Path(__file__).resolve().parents[2] / "metrics.tsv"
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    biological = [row for row in rows if row["evidence_track"] == "biological_validation"]
    assert biological
    assert all(row["source_run_id"] for row in biological)
    assert all(row["source_standard_table"] for row in biological)
    assert all(len(row["source_standard_table_sha256"]) == 64 for row in biological)
