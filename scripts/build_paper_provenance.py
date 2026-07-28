#!/usr/bin/env python3
"""Bind ABI paper metrics and figures to auditable run evidence."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from abi.evidence import build_evidence_manifest, derive_run_id
from abi.workflow.manifest import checksum_file

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "metrics.tsv"
MANIFEST_DIR = ROOT / "docs/paper_examples/manifests"
SOURCE_FIELDS = [
    "source_run_id",
    "source_standard_table",
    "source_standard_table_sha256",
]


@dataclass(frozen=True)
class SourceBinding:
    run_id: str
    artifact: Path

    def columns(self) -> dict[str, str]:
        return {
            "source_run_id": self.run_id,
            "source_standard_table": self.artifact.relative_to(ROOT).as_posix(),
            "source_standard_table_sha256": checksum_file(self.artifact),
        }


def _run_binding(result_dir: str, table: str) -> SourceBinding:
    root = ROOT / result_dir
    return SourceBinding(derive_run_id(root), root / "tables" / table)


def _external_binding(evidence_id: str, artifact: str) -> SourceBinding:
    path = ROOT / artifact
    return SourceBinding(f"evidence-sha256:{checksum_file(path)}:{evidence_id}", path)


def source_bindings() -> dict[str, SourceBinding]:
    return {
        "airway": _run_binding("downloads/rnaseq_retry5", "differential_expression.tsv"),
        "wgs_mlst": _run_binding("downloads/wgs_st93_mrsa_retry", "mlst_profile.tsv"),
        "wgs_amr": _run_binding("downloads/wgs_st93_mrsa_retry", "amr_profile.tsv"),
        "wgs_external": _external_binding(
            "wgs-snp-comparison", "docs/paper_examples/wgs_snp_pairwise_distances.tsv"
        ),
        "scapp_core": _run_binding("downloads/plasmid_scapp_core_retry7", "plasmid_consensus.tsv"),
        "scapp_node": _run_binding("downloads/abi_scapp", "plasmid_predictions.tsv"),
        "scapp_external": _external_binding(
            "scapp-original-comparison", "downloads/scapp_original/three_way_comparison.tsv"
        ),
    }


def binding_for_metric(
    row: dict[str, str],
    bindings: dict[str, SourceBinding],
) -> SourceBinding | None:
    if row.get("evidence_track") != "biological_validation":
        return None
    workflow = row.get("model_or_workflow", "")
    dataset = row.get("dataset_or_suite", "")
    metric = row.get("metric", "")
    if workflow == "rnaseq_expression":
        return bindings["airway"]
    if workflow == "wgs_bacteria":
        amr_metrics = {"mecA_concordance", "amr_standard_table_rows"}
        return bindings["wgs_amr"] if metric in amr_metrics else bindings["wgs_mlst"]
    if workflow in {"spandx_v2_6_paper_track", "abi_bcftools_track"}:
        return bindings["wgs_external"]
    if workflow == "metagenomic_plasmid":
        if "original reproduction" in dataset:
            return bindings["scapp_external"]
        if "ABI SCAPP node" in dataset:
            return bindings["scapp_node"]
        return bindings["scapp_core"]
    return None


def annotate_metrics(path: Path = METRICS_PATH) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for field in SOURCE_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    bindings = source_bindings()
    for row in rows:
        binding = binding_for_metric(row, bindings)
        values = binding.columns() if binding else {field: "" for field in SOURCE_FIELDS}
        row.update(values)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _case_paths(case: str) -> list[Path]:
    shared = [METRICS_PATH]
    if case == "airway":
        root = ROOT / "downloads/rnaseq_retry5"
        return shared + [
            root / "provenance/run_summary.json",
            root / "provenance/commands.tsv",
            root / "provenance/resolved_inputs.tsv",
            root / "provenance/tool_versions.tsv",
            root / "provenance/resources.json",
            root / "provenance/checksums.json",
            root / "tables/differential_expression.tsv",
            ROOT / "docs/paper_examples/airway_metrics.tsv",
            ROOT / "docs/_static/paper_examples/airway_validation.provenance.json",
        ]
    if case == "wgs":
        root = ROOT / "downloads/wgs_st93_mrsa_retry"
        return shared + [
            root / "provenance/run_summary.json",
            root / "provenance/commands.tsv",
            root / "provenance/resolved_inputs.tsv",
            root / "provenance/tool_versions.tsv",
            root / "provenance/resources.json",
            root / "provenance/checksums.json",
            root / "tables/mlst_profile.tsv",
            root / "tables/amr_profile.tsv",
            ROOT / "docs/paper_examples/wgs_metrics.tsv",
            ROOT / "docs/paper_examples/wgs_snp_pairwise_distances.tsv",
            ROOT / "docs/_static/paper_examples/wgs_validation.provenance.json",
        ]
    if case == "scapp":
        core = ROOT / "downloads/plasmid_scapp_core_retry7"
        node = ROOT / "downloads/abi_scapp"
        return shared + [
            core / "provenance/run_summary.json",
            core / "provenance/commands.tsv",
            core / "provenance/checksums.json",
            core / "tables/plasmid_consensus.tsv",
            node / "provenance/run_summary.json",
            node / "provenance/commands.tsv",
            node / "provenance/checksums.json",
            node / "tables/plasmid_predictions.tsv",
            ROOT
            / (
                "docs/zh/figures/data/scapp_paper_method_v2_20260724/machine_readable_evidence.json"
            ),
            ROOT / "downloads/scapp_original/three_way_comparison.tsv",
            ROOT / "docs/_static/paper_examples/scapp_descriptive_evidence.provenance.json",
        ]
    raise ValueError(f"Unknown paper case: {case}")


def build_case_manifests() -> dict[str, str]:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    bindings = source_bindings()
    run_ids = {
        "airway": bindings["airway"].run_id,
        "wgs": bindings["wgs_mlst"].run_id,
        "scapp": bindings["scapp_core"].run_id,
    }
    outputs = {}
    for case, run_id in run_ids.items():
        output = MANIFEST_DIR / f"{case}.evidence-manifest.json"
        build_evidence_manifest(
            artifact_root=ROOT,
            paths=_case_paths(case),
            output=output,
            evidence_id=f"abi-paper-{case}",
            run_id=run_id,
        )
        outputs[case] = output.relative_to(ROOT).as_posix()
    return outputs


def main() -> int:
    annotate_metrics()
    print(json.dumps(build_case_manifests(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
