"""Normalize pinned Bacannot v3.4.4 outputs into stable ABI tables."""

from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from abi.external_workflows.evidence import sha256_file
from abi.external_workflows.models import ExternalProcessContract, ExternalTaskAttempt

from .artifacts import evaluate_required_outputs

PARSER_VERSION = "bacannot-3.4.4-parser-v1"


def normalize_bacannot_outputs(
    output_root: str | Path,
    result_root: str | Path,
    attempts: Iterable[ExternalTaskAttempt],
    contracts: Iterable[ExternalProcessContract],
    schemas: Mapping[str, Iterable[str]],
    *,
    modules: Mapping[str, Any],
    sample_ids: Iterable[str],
) -> Mapping[str, Path]:
    output = Path(output_root)
    result = Path(result_root)
    attempts = list(attempts)
    contracts = list(contracts)
    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in schemas}
    samples = sorted(set(sample_ids))
    for sample_id in samples:
        sample_root = output / sample_id
        assembly = _first_file(
            sample_root.glob("assembly/**/assembly.fasta"),
            sample_root.glob("annotation/*.fna"),
        )
        if assembly:
            stats = _assembly_stats(assembly)
            rows["genome_assembly_stats"].append(
                _source_row(sample_id, assembly, attempts, "assembly", stats)
            )
            for metric, value, unit in (
                ("assembly_total_length", stats["total_length"], "bp"),
                ("assembly_contigs", stats["num_contigs"], "count"),
                ("assembly_n50", stats["n50"], "bp"),
            ):
                rows["qc_summary"].append(
                    _source_row(
                        sample_id,
                        assembly,
                        attempts,
                        "assembly",
                        {"metric": metric, "value": value, "unit": unit},
                    )
                )
        gff = next(iter(sorted(sample_root.glob("annotation/*.gff"))), None)
        if gff:
            counts = _gff_counts(gff)
            rows["genome_annotation"].append(
                _source_row(sample_id, gff, attempts, "annotation", counts)
            )
        mlst = next(iter(sorted(sample_root.glob("MLST/*_mlst_analysis.txt"))), None)
        if mlst:
            rows["mlst_profile"].append(
                _source_row(sample_id, mlst, attempts, "mlst", _mlst_row(mlst))
            )
        for amr in sorted(
            sample_root.glob("resistance/AMRFinderPlus/AMRFinder_resistance-only.tsv")
        ):
            for parsed in _amr_rows(amr):
                rows["amr_profile"].append(_source_row(sample_id, amr, attempts, "amr", parsed))
        for contract in contracts:
            status = (
                _contract_status(sample_id, sample_root, attempts, contract)
                if modules.get(contract.process_class, True) is True
                else "not_selected"
            )
            rows["sample_status"].append(
                {
                    "sample_id": sample_id,
                    "contract_id": contract.contract_id,
                    "status": status,
                    "publishable": str(status == "passed").lower(),
                    "evidence_reference": "provenance/task_attempts.tsv",
                }
            )
    paths: dict[str, Path] = {}
    standard = result / "standard"
    tables = result / "tables"
    standard.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    source_rows: list[dict[str, str]] = []
    for table_name, columns_value in schemas.items():
        columns = list(columns_value)
        path = standard / f"{table_name}.tsv"
        _write_tsv(path, columns, rows.get(table_name, []))
        shutil.copyfile(path, tables / path.name)
        paths[table_name] = path
        for index, row in enumerate(rows.get(table_name, []), start=1):
            if row.get("source_file"):
                source_rows.append(
                    {
                        "table_name": table_name,
                        "row_id": _row_id(table_name, index, row),
                        "sample_id": str(row.get("sample_id", "")),
                        "source_file": str(row.get("source_file", "")),
                        "source_file_sha256": str(row.get("source_file_sha256", "")),
                        "external_task_id": str(row.get("external_task_id", "")),
                        "process_name": str(row.get("process_name", "")),
                        "parser_version": PARSER_VERSION,
                    }
                )
    sources_path = result / "provenance" / "result_sources.tsv"
    _write_tsv(
        sources_path,
        [
            "table_name",
            "row_id",
            "sample_id",
            "source_file",
            "source_file_sha256",
            "external_task_id",
            "process_name",
            "parser_version",
        ],
        source_rows,
    )
    paths["result_sources"] = sources_path
    return paths


def _source_row(
    sample_id: str,
    source: Path,
    attempts: list[ExternalTaskAttempt],
    process_class: str,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    attempt = next(
        (
            row
            for row in reversed(attempts)
            if row.sample_id == sample_id
            and row.process_class == process_class
            and row.status in {"COMPLETED", "CACHED"}
        ),
        None,
    )
    return {
        "sample_id": sample_id,
        **values,
        "source_file": str(source),
        "source_file_sha256": sha256_file(source),
        "external_task_id": attempt.task_id if attempt else "",
        "process_name": attempt.process_name if attempt else "",
        "tool_id": process_class,
        "tool_version": "recorded_in_bacannot_tools_versioning",
        "database_id": "bacannot_db",
        "database_version": "recorded_in_external_plan_snapshot",
        "parser_version": PARSER_VERSION,
    }


def _first_file(*iterables: Iterable[Path]) -> Path | None:
    for iterable in iterables:
        candidate = next(iter(sorted(iterable)), None)
        if candidate and candidate.is_file():
            return candidate
    return None


def _assembly_stats(path: Path) -> dict[str, Any]:
    sequences: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if current:
                sequences.append("".join(current))
            current = []
        else:
            current.append(line.strip())
    if current:
        sequences.append("".join(current))
    lengths = sorted((len(value) for value in sequences), reverse=True)
    total = sum(lengths)
    cumulative = 0
    n50 = 0
    for length in lengths:
        cumulative += length
        if cumulative >= total / 2:
            n50 = length
            break
    gc = sum(value.upper().count("G") + value.upper().count("C") for value in sequences)
    return {
        "total_length": total,
        "num_contigs": len(lengths),
        "n50": n50,
        "max_contig_length": max(lengths, default=0),
        "gc_content": round((gc / total * 100), 3) if total else "",
    }


def _gff_counts(path: Path) -> dict[str, int]:
    counts = {"cds_count": 0, "rrna_count": 0, "trna_count": 0}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        feature = parts[2].lower()
        if feature == "cds":
            counts["cds_count"] += 1
        elif feature == "rrna":
            counts["rrna_count"] += 1
        elif feature == "trna":
            counts["trna_count"] += 1
    return counts


def _mlst_row(path: Path) -> dict[str, str]:
    line = next((value for value in path.read_text(encoding="utf-8").splitlines() if value), "")
    fields = line.split("\t")
    scheme = fields[1] if len(fields) > 1 else "unknown"
    sequence_type = fields[2] if len(fields) > 2 else "no_hit"
    alleles = fields[3:] if len(fields) > 3 else []
    return {
        "scheme": scheme or "unknown",
        "sequence_type": sequence_type or "no_hit",
        "allele_status": ";".join(alleles) if alleles else "no_hit",
    }


def _amr_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            {
                "gene_symbol": row.get("Gene symbol", "") or row.get("Gene", ""),
                "target_class": row.get("Class", ""),
                "method": row.get("Method", ""),
                "identity_pct": row.get("% Identity to reference sequence", ""),
                "coverage_pct": row.get("% Coverage of reference sequence", ""),
            }
            for row in csv.DictReader(handle, delimiter="\t")
        ]


def _contract_status(
    sample_id: str,
    sample_root: Path,
    attempts: list[ExternalTaskAttempt],
    contract: ExternalProcessContract,
) -> str:
    observed = [
        row
        for row in attempts
        if row.sample_id == sample_id and row.process_class == contract.process_class
    ]
    successful = [row for row in observed if row.status in contract.accepted_statuses]
    if not observed:
        return "missing_process"
    if not successful:
        return "process_failed"
    missing, invalid = evaluate_required_outputs(contract.required_outputs, sample_root)
    if missing:
        return "artifact_missing"
    if invalid:
        return "artifact_invalid"
    return "passed"


def _write_tsv(path: Path, columns: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def _row_id(table_name: str, index: int, row: Mapping[str, Any]) -> str:
    payload = (
        f"{table_name}\0{index}\0{row.get('sample_id', '')}\0{row.get('source_file_sha256', '')}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
