#!/usr/bin/env python3
"""Create biological paper figures for the Airway, WGS, and SCAPP case studies.

The script intentionally uses only frozen, claim-eligible case-study evidence. It does not read
or import any ABI-Bench outcome. SCAPP reference-match fields are excluded because the historical
single-stage match screen is not valid paper-method truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAPP_SOURCE = ROOT / "docs/zh/figures/data/scapp_evidence_20260720/evidence_by_plasmid.tsv"
DATA_DIR = ROOT / "docs/paper_examples"
FIGURE_DIR = ROOT / "docs/_static/paper_examples"
INK = "#222222"
BLUE = "#0072B2"
ORANGE = "#E69F00"
GREY = "#B8B8B8"


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _save_figure(fig: plt.Figure, basename: str) -> list[str]:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    for suffix in ("png", "pdf", "svg"):
        path = FIGURE_DIR / f"{basename}.{suffix}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        if suffix == "svg":
            # matplotlib emits trailing spaces in SVG path data; strip them so the
            # repository `git diff --check` gate stays green across regenerations.
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")
        outputs.append(_display_path(path))
    plt.close(fig)
    return outputs


def create_airway_figure() -> dict[str, Any]:
    metrics_path = DATA_DIR / "airway_metrics.tsv"
    metrics = {row["metric"]: row for row in _read_tsv(metrics_path)}
    overlap = int(metrics["significant_gene_overlap"]["estimate"])
    abi_total = int(metrics["abi_mapped_significant_genes"]["estimate"])
    geo_total = int(metrics["geo_mapped_significant_genes"]["estimate"])
    abi_only = abi_total - overlap
    geo_only = geo_total - overlap
    jaccard = overlap / (abi_total + geo_total - overlap)
    documented = float(metrics["significant_set_jaccard"]["estimate"])
    if abs(jaccard - documented) > 0.0001:
        raise ValueError(f"Airway Jaccard mismatch: computed={jaccard}, documented={documented}")

    rows = [
        {"set_region": "ABI_only", "gene_count": abi_only},
        {"set_region": "shared", "gene_count": overlap},
        {"set_region": "GEO_only", "gene_count": geo_only},
    ]
    data_path = DATA_DIR / "airway_significant_set_overlap.tsv"
    _write_tsv(data_path, ["set_region", "gene_count"], rows)

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Circle((0.43, 0.53), 0.32, color=BLUE, alpha=0.34, ec=BLUE, lw=2))
    ax.add_patch(Circle((0.70, 0.53), 0.18, color=ORANGE, alpha=0.42, ec=ORANGE, lw=2))
    ax.text(0.26, 0.55, f"ABI only\n{abi_only:,}", ha="center", va="center", fontsize=10)
    ax.text(0.56, 0.55, f"Shared\n{overlap:,}", ha="center", va="center", fontsize=10)
    ax.text(0.78, 0.55, f"GEO only\n{geo_only:,}", ha="center", va="center", fontsize=10)
    ax.text(0.29, 0.88, f"ABI significant (mapped)\nn={abi_total:,}", ha="center", color=INK)
    ax.text(0.76, 0.80, f"GEO significant\nn={geo_total:,}", ha="center", color=INK)
    ax.text(
        0.50,
        0.11,
        "Effect evidence: Spearman ρ=0.927 · direction=90.8% · sentinel genes=7/7\n"
        f"Significant-set Jaccard={documented:.4f}; schematic circles are not area-proportional",
        ha="center",
        va="center",
        fontsize=9,
        color=INK,
    )
    ax.set_xlim(0.02, 0.98)
    ax.set_ylim(0.02, 0.98)
    ax.set_title("Airway Dex-response agreement across analysis methods", fontsize=13, pad=10)
    outputs = _save_figure(fig, "airway_biological_validation")
    return {
        "figure_id": "airway_biological_validation",
        "source": _display_path(metrics_path),
        "source_sha256": _sha256(metrics_path),
        "data": _display_path(data_path),
        "outputs": outputs,
        "claim": "method-sensitive significant-set overlap with strong effect-direction evidence",
    }


def _snp_matrix(rows: list[dict[str, str]], samples: list[str]) -> list[list[float]]:
    index = {sample: position for position, sample in enumerate(samples)}
    matrix = [[0.0] * len(samples) for _ in samples]
    for row in rows:
        i, j = index[row["sample_a"]], index[row["sample_b"]]
        distance = float(row["snp_distance"])
        matrix[i][j] = matrix[j][i] = distance
    for position in range(len(samples)):
        matrix[position][position] = float("nan")
    return matrix


def create_wgs_figure() -> dict[str, Any]:
    metrics_path = DATA_DIR / "wgs_metrics.tsv"
    metrics = {row["metric"]: row for row in _read_tsv(metrics_path)}
    if metrics["ST93_concordance"]["numerator"] != "6":
        raise ValueError("WGS ST93 evidence must contain six positive isolates")
    if metrics["mecA_concordance"]["numerator"] != "6":
        raise ValueError("WGS mecA evidence must contain six positive isolates")

    pairwise_path = DATA_DIR / "wgs_snp_pairwise_distances.tsv"
    pairwise_rows = _read_tsv(pairwise_path)
    samples = [f"SRR205703{index}" for index in range(6)]
    tracks: dict[str, list[dict[str, str]]] = {"paper_spandx": [], "abi_bcftools": []}
    for row in pairwise_rows:
        if row["track"] not in tracks:
            raise ValueError(f"Unexpected WGS SNP track: {row['track']}")
        if row["sample_a"] not in samples or row["sample_b"] not in samples:
            raise ValueError(f"Unexpected WGS SNP sample pair: {row}")
        tracks[row["track"]].append(row)
    expected_ranges = {"paper_spandx": (7, 60), "abi_bcftools": (10, 73)}
    for track, rows in tracks.items():
        if len(rows) != 15:
            raise ValueError(f"Expected 15 {track} pairs, found {len(rows)}")
        distances = [int(row["snp_distance"]) for row in rows]
        minimum = int(metrics[f"{track}_pairwise_snp_min"]["estimate"])
        maximum = int(metrics[f"{track}_pairwise_snp_max"]["estimate"])
        if (min(distances), max(distances)) != (minimum, maximum):
            raise ValueError(f"{track} pairwise range disagrees with wgs_metrics.tsv")
        if (minimum, maximum) != expected_ranges[track]:
            raise ValueError(f"{track} range {minimum}-{maximum} contradicts the frozen comparison")

    evidence_rows: list[dict[str, Any]] = []
    for isolate in range(1, 7):
        evidence_rows.extend(
            [
                {"study_isolate": isolate, "endpoint": "ST93", "state": "recovered"},
                {"study_isolate": isolate, "endpoint": "mecA", "state": "recovered"},
                {
                    "study_isolate": isolate,
                    "endpoint": "core-SNP",
                    "state": "pairwise_context_recovered_external_track",
                },
            ]
        )
    data_path = DATA_DIR / "wgs_isolate_evidence.tsv"
    _write_tsv(data_path, ["study_isolate", "endpoint", "state"], evidence_rows)

    labels = [f"I{index}" for index in range(1, 7)]
    fig = plt.figure(figsize=(11.5, 3.6))
    grid = fig.add_gridspec(1, 4, width_ratios=[1.15, 1.0, 1.0, 0.045], wspace=0.32)

    ax_grid = fig.add_subplot(grid[0, 0])
    matrix = [[1] * 6, [1] * 6, [1] * 6]
    ax_grid.imshow(matrix, cmap=ListedColormap([GREY, BLUE]), vmin=0, vmax=1, aspect="auto")
    for row_index, values in enumerate(matrix):
        for column_index, value in enumerate(values):
            ax_grid.text(column_index, row_index, "✓", ha="center", va="center", color="white")
    ax_grid.set_xticks(range(6), labels)
    ax_grid.set_yticks(
        range(3), ["ST93 MLST", "Full-length mecA", "External core-SNP range 7-60"]
    )
    ax_grid.set_title("Study endpoint and comparator recovery", fontsize=11, pad=8)
    ax_grid.set_xlabel("Study isolate (I1-I6 = SRR2057030-35)")
    for spine in ax_grid.spines.values():
        spine.set_visible(False)

    heatmap_panels = [
        ("paper_spandx", "Paper track: SPANDx v2.6 (82-sample matrix)"),
        ("abi_bcftools", "ABI-adjacent track: bcftools joint calling"),
    ]
    image = None
    for column, (track, title) in enumerate(heatmap_panels, start=1):
        ax = fig.add_subplot(grid[0, column])
        masked = [row[:] for row in _snp_matrix(tracks[track], samples)]
        image = ax.imshow(masked, cmap="viridis", vmin=0, vmax=80, aspect="auto")
        for i in range(6):
            for j in range(6):
                if i != j:
                    ax.text(
                        j,
                        i,
                        f"{masked[i][j]:.0f}",
                        ha="center",
                        va="center",
                        fontsize=7.5,
                        color="white" if masked[i][j] < 40 else INK,
                    )
        ax.set_xticks(range(6), labels, fontsize=8)
        ax.set_yticks(range(6), labels if column == 1 else [""] * 6, fontsize=8)
        minimum, maximum = expected_ranges[track]
        ax.set_title(f"{title}\nrange {minimum}-{maximum}", fontsize=10, pad=8)
    colorbar_ax = fig.add_subplot(grid[0, 3])
    if image is None:
        raise ValueError("WGS SNP heatmaps were not rendered")
    fig.colorbar(image, cax=colorbar_ax, label="Pairwise SNP distance")
    fig.text(
        0.5,
        0.02,
        "Published six-isolate range: 7-60 SNPs (mean 44). Paper track recovers the "
        "pairwise-distance endpoint; full outbreak conclusions also require tree/context "
        "evidence. The ABI-adjacent bcftools track yields 10-73 and is not the paper method.",
        ha="center",
        va="bottom",
        fontsize=8.5,
        color=INK,
    )
    fig.subplots_adjust(left=0.13, right=0.99, top=0.80, bottom=0.20)
    outputs = _save_figure(fig, "wgs_biological_validation")
    return {
        "figure_id": "wgs_biological_validation",
        "source": _display_path(metrics_path),
        "source_sha256": _sha256(metrics_path),
        "data": _display_path(data_path),
        "pairwise_data": _display_path(pairwise_path),
        "outputs": outputs,
        "claim": "ST93/mecA recovery plus paper-track core-SNP pairwise-distance endpoint recovery",
    }


def create_scapp_figure(source_path: Path) -> dict[str, Any]:
    source_rows = _read_tsv(source_path)
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
    rows = [{field: row[field] for field in fields} for row in source_rows]
    if len(rows) != 157:
        raise ValueError(f"Expected 157 SCAPP consensus candidates, found {len(rows)}")
    data_path = DATA_DIR / "scapp_biological_evidence.tsv"
    _write_tsv(data_path, fields, rows)

    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    categories = [
        ("non-mobilizable", "False", BLUE, "o", "Non-mobilizable, no terminal overlap"),
        ("non-mobilizable", "True", BLUE, "s", "Non-mobilizable, terminal overlap"),
        ("mobilizable", "False", ORANGE, "^", "Mobilizable, no terminal overlap"),
        ("mobilizable", "True", ORANGE, "D", "Mobilizable, terminal overlap"),
    ]
    for mobility, circular, color, marker, label in categories:
        selected = [
            row
            for row in rows
            if row["predicted_mobility"] == mobility and row["is_circular"] == circular
        ]
        if not selected:
            continue
        ax.scatter(
            [float(row["log10_length_bp"]) for row in selected],
            [float(row["log10_abundance_coverage"]) for row in selected],
            s=30,
            c=color,
            marker=marker,
            alpha=0.72,
            edgecolors=INK if marker != "o" else "none",
            linewidths=0.5,
            label=f"{label} (n={len(selected)})",
        )
    amr_rows = [row for row in rows if int(row["amr_hit_count"]) > 0]
    for row in amr_rows:
        x_value = float(row["log10_length_bp"])
        y_value = float(row["log10_abundance_coverage"])
        ax.scatter([x_value], [y_value], s=105, marker="*", c="white", ec=INK, lw=1.0, zorder=5)
        ax.annotate(
            f"AMR-supported {row['plasmid_id']}",
            (x_value, y_value),
            xytext=(6, 7),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Consensus plasmid length (log10 bp)")
    ax.set_ylabel("CoverM abundance coverage (log10)")
    ax.set_title("SCAPP consensus plasmids span abundance, length, and mobility evidence")
    ax.grid(True, color="#E3E3E3", linewidth=0.7, zorder=0)
    ax.legend(fontsize=7.5, frameon=False, loc="best")
    ax.text(
        0.01,
        0.01,
        "Descriptive panel; paper-method P/R/F1 reported separately (not paper-exact).",
        transform=ax.transAxes,
        fontsize=8,
        color=INK,
    )
    outputs = _save_figure(fig, "scapp_biological_evidence")
    return {
        "figure_id": "scapp_biological_evidence",
        "source": _display_path(source_path),
        "source_sha256": _sha256(source_path),
        "data": _display_path(data_path),
        "outputs": outputs,
        "claim": "descriptive length-abundance and auxiliary mobility evidence; not accuracy",
    }


def create_figures(scapp_source: Path = DEFAULT_SCAPP_SOURCE) -> dict[str, Any]:
    if not scapp_source.is_file():
        raise FileNotFoundError(f"Missing frozen SCAPP evidence table: {scapp_source}")
    results = [
        create_airway_figure(),
        create_wgs_figure(),
        create_scapp_figure(scapp_source),
    ]
    provenance = {
        "schema_version": "abi.paper_case_study_figures.v1",
        "benchmark_outcomes_used": False,
        "generator": _display_path(Path(__file__).resolve()),
        "generator_sha256": _sha256(Path(__file__).resolve()),
        "figures": results,
    }
    path = FIGURE_DIR / "biological_figures.provenance.json"
    path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scapp-source", type=Path, default=DEFAULT_SCAPP_SOURCE)
    args = parser.parse_args()
    result = create_figures(args.scapp_source.resolve())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
