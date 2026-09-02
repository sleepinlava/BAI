"""L3 result validation for Bacannot task contracts and evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, cast

from abi.external_workflows.evidence import sha256_file, verify_evidence_manifest
from abi.external_workflows.models import ExternalProcessContract, ExternalTaskAttempt

from .artifacts import evaluate_required_outputs


def validate_bacannot_result(
    result_dir: str | Path,
    contracts: Iterable[ExternalProcessContract],
    *,
    allow_empty_tables: bool,
    sample_output_root: str | Path | None = None,
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
    resolved_config = snapshot.get("resolved_config", {})
    audit = resolved_config.get("audit", {}) if isinstance(resolved_config, Mapping) else {}
    unmapped_policy = (
        str(audit.get("unmapped_policy", "warn")) if isinstance(audit, Mapping) else "warn"
    )
    unmapped = [row for row in attempts if row.process_class == "unmapped"]
    if unmapped_policy == "fail" and unmapped:
        errors.append(
            {
                "error_code": "UNMAPPED_PROCESSES",
                "message": (
                    f"{len(unmapped)} task attempt(s) match no process contract; "
                    "update the contract set before production publication"
                ),
                "process_names": sorted({row.process_name for row in unmapped}),
            }
        )
    sample_root = (
        Path(sample_output_root) if sample_output_root is not None else root / "raw" / "bacannot"
    )
    contract_status: list[dict[str, Any]] = []
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
            evidence_row = successful[-1] if successful else None
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
            missing: list[dict[str, Any]] = []
            invalid: list[dict[str, Any]] = []
            if status == "passed":
                missing, invalid = evaluate_required_outputs(
                    contract.required_outputs, sample_root / sample_id
                )
                if missing:
                    status = "artifact_missing"
                elif invalid:
                    status = "artifact_invalid"
            contract_status.append(
                {
                    "sample_id": sample_id,
                    "contract_id": contract.contract_id,
                    "status": status,
                    "external_task_id": evidence_row.task_id if evidence_row else "",
                    "task_hash": evidence_row.task_hash if evidence_row else "",
                    "missing_outputs": missing,
                    "invalid_outputs": invalid,
                }
            )
            if status not in {"passed", "not_selected", "not_applicable"}:
                error: dict[str, Any] = {
                    "error_code": "PROCESS_CONTRACT_FAILED",
                    "sample_id": sample_id,
                    "contract_id": contract.contract_id,
                    "status": status,
                }
                if evidence_row is not None:
                    error["external_task_id"] = evidence_row.task_id
                if missing:
                    error["missing_outputs"] = missing
                if invalid:
                    error["invalid_outputs"] = invalid
                errors.append(error)
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
    standard = root / "standard"
    required_tables = ["qc_summary.tsv", "genome_assembly_stats.tsv", "genome_annotation.tsv"]
    if modules.get("mlst", True) is True:
        required_tables.append("mlst_profile.tsv")
    if modules.get("amr", True) is True:
        required_tables.append("amr_profile.tsv")
    required_tables.append("sample_status.tsv")
    for name in required_tables:
        path = standard / name
        if not path.is_file():
            errors.append({"error_code": "OUTPUT_PARSE_FAILED", "message": f"Missing {name}"})
            continue
        if not allow_empty_tables and path.stat().st_size == 0:
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
