"""L3 result validation for Bacannot task contracts and evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, cast

from abi.external_workflows.evidence import sha256_file, verify_evidence_manifest
from abi.external_workflows.models import ExternalProcessContract, ExternalTaskAttempt


def validate_bacannot_result(
    result_dir: str | Path,
    contracts: Iterable[ExternalProcessContract],
    *,
    allow_empty_tables: bool,
) -> Mapping[str, Any]:
    root = Path(result_dir)
    errors: list[dict[str, Any]] = []
    manifest = root / "provenance" / "evidence_manifest.json"
    if not manifest.is_file():
        errors.append({"error_code": "EVIDENCE_INCOMPLETE", "message": str(manifest)})
    else:
        verified = verify_evidence_manifest(manifest)
        if not verified["valid"]:
            errors.append({"error_code": "EVIDENCE_INCOMPLETE", "details": verified["errors"]})
        _check_live_evidence_matches_manifest(
            manifest,
            {
                "external_plan_snapshot": root / "provenance" / "external_plan_snapshot.json",
                "task_attempts": root / "provenance" / "task_attempts.tsv",
            },
            errors,
        )
    attempts_path = root / "provenance" / "task_attempts.tsv"
    attempts = _read_attempts(attempts_path)
    snapshot_path = root / "provenance" / "external_plan_snapshot.json"
    snapshot: Mapping[str, Any] = {}
    if snapshot_path.is_file():
        loaded = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            snapshot = loaded
    else:
        errors.append({"error_code": "EVIDENCE_INCOMPLETE", "message": str(snapshot_path)})
    snapshot_samples = {
        str(row.get("sample_id", ""))
        for row in snapshot.get("inputs", [])
        if isinstance(row, Mapping) and row.get("sample_id")
    }
    samples = sorted(snapshot_samples | {row.sample_id for row in attempts if row.sample_id})
    if not samples:
        errors.append(
            {"error_code": "EVIDENCE_INCOMPLETE", "message": "No expected samples recorded"}
        )
    modules = snapshot.get("modules", {})
    if not isinstance(modules, Mapping):
        modules = {}
    contract_status: list[dict[str, str]] = []
    for contract in contracts:
        for sample_id in samples:
            if modules and modules.get(contract.process_class, True) is not True:
                contract_status.append(
                    {
                        "sample_id": sample_id,
                        "contract_id": contract.contract_id,
                        "status": "not_selected",
                    }
                )
                continue
            observed = [
                row
                for row in attempts
                if row.sample_id == sample_id and row.process_class == contract.process_class
            ]
            successful = [row for row in observed if row.status in contract.accepted_statuses]
            if not observed:
                status = "missing_process"
            elif not successful:
                status = "process_failed"
            elif len(successful) < contract.min_successful_per_sample:
                status = "missing_process"
            elif (
                contract.max_successful_final_per_sample is not None
                and len(successful) > contract.max_successful_final_per_sample
            ):
                status = "process_failed"
            else:
                status = "passed"
            contract_status.append(
                {
                    "sample_id": sample_id,
                    "contract_id": contract.contract_id,
                    "status": status,
                }
            )
            if status not in {"passed", "not_selected", "not_applicable"}:
                errors.append(
                    {
                        "error_code": "PROCESS_CONTRACT_FAILED",
                        "sample_id": sample_id,
                        "contract_id": contract.contract_id,
                        "status": status,
                    }
                )
    sample_status = root / "standard" / "sample_status.tsv"
    if sample_status.is_file():
        with sample_status.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                status = str(row.get("status", ""))
                if status not in {"passed", "not_selected", "not_applicable"}:
                    errors.append(
                        {
                            "error_code": "PROCESS_CONTRACT_FAILED",
                            "sample_id": row.get("sample_id", ""),
                            "contract_id": row.get("contract_id", ""),
                            "status": status,
                        }
                    )
    if not allow_empty_tables:
        standard = root / "standard"
        for name in (
            "qc_summary.tsv",
            "genome_assembly_stats.tsv",
            "genome_annotation.tsv",
            "sample_status.tsv",
        ):
            path = standard / name
            if not path.is_file() or path.stat().st_size == 0:
                errors.append({"error_code": "OUTPUT_PARSE_FAILED", "message": f"Empty {name}"})
    return {"valid": not errors, "errors": errors, "contracts": contract_status}


def _check_live_evidence_matches_manifest(
    manifest_path: Path,
    live_paths: Mapping[str, Path],
    errors: list[dict[str, Any]],
) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksums = {
        str(row.get("type")): str(row.get("sha256", ""))
        for row in payload.get("files", [])
        if isinstance(row, Mapping)
    }
    for evidence_type, path in live_paths.items():
        expected = checksums.get(evidence_type)
        if expected is None:
            # Older/test bundles may not carry ABI-derived evidence, but a
            # managed production run always does.
            continue
        if not path.is_file() or sha256_file(path) != expected:
            errors.append(
                {
                    "error_code": "EVIDENCE_INCOMPLETE",
                    "message": f"Live {evidence_type} differs from archived evidence",
                }
            )


def _read_attempts(path: Path) -> list[ExternalTaskAttempt]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    allowed = set(ExternalTaskAttempt.__dataclass_fields__)
    attempts = []
    for row in rows:
        values = {key: value for key, value in row.items() if key in allowed}
        values["attempt"] = int(values.get("attempt") or 1)
        for key in (
            "duration_ms",
            "requested_memory_bytes",
            "peak_rss_bytes",
            "peak_vmem_bytes",
        ):
            values[key] = int(values[key]) if values.get(key) else None
        values["requested_cpus"] = (
            float(values["requested_cpus"]) if values.get("requested_cpus") else None
        )
        attempts.append(ExternalTaskAttempt(**cast(Any, values)))
    return attempts
