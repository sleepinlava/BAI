"""Independent, machine-readable ABI result compliance auditing."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from abi.filesystem import checksum_file, checksum_path
from abi.interfaces import ABIComplianceAuditPlugin
from abi.plugin_registry import get_plugin


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    """Compute the file's SHA-256 via the canonical implementation (P1-4)."""
    return checksum_file(path)


def _tool_check(path: Path) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    if path.is_file():
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
    failures = [
        str(row.get("tool_id", ""))
        for row in rows
        if row.get("status") != "captured" or not str(row.get("version", "")).strip()
    ]
    return {"pass": bool(rows) and not failures, "tool_count": len(rows), "failures": failures}


def _resource_check(path: Path, required_ids: set[str]) -> dict[str, Any]:
    resources = _json(path).get("resources", [])
    failures = []
    for resource in resources if isinstance(resources, list) else []:
        if required_ids and str(resource.get("id", "")) not in required_ids:
            continue
        if any(
            not str(resource.get(field, "")).strip()
            for field in ("id", "path", "version", "source_url", "checksum_sha256")
        ):
            failures.append(str(resource.get("id", "unknown")))
            continue
        if checksum_path(resource["path"]) != resource["checksum_sha256"]:
            failures.append(str(resource.get("id", "unknown")) + ":checksum_mismatch")
    checked = [
        resource
        for resource in resources
        if isinstance(resources, list)
        if not required_ids or str(resource.get("id", "")) in required_ids
    ]
    return {
        "pass": bool(checked) and not failures,
        "resource_count": len(checked),
        "failures": failures,
    }


def _checksum_check(root: Path, provenance: Path) -> dict[str, Any]:
    checksums = _json(provenance / "checksums.json")
    tombstones: dict[str, str] = {}
    for manifest in sorted((provenance / "tombstones").glob("*.json")):
        for artifact in _json(manifest).get("artifacts", []):
            if artifact.get("status") == "deleted":
                tombstones[str(artifact.get("path", ""))] = str(artifact.get("sha256", ""))
    statuses: list[dict[str, str]] = []
    for recorded_path, expected in checksums.items():
        path = Path(recorded_path)
        if not path.is_absolute():
            path = root / path
        if path.is_file():
            status = "present_verified" if _sha256(path) == expected else "mismatched"
        elif tombstones.get(recorded_path) == expected or tombstones.get(str(path)) == expected:
            status = "deleted_tombstoned"
        else:
            status = "unexplained_missing"
        statuses.append({"path": recorded_path, "status": status})
    counts = Counter(item["status"] for item in statuses)
    summary = {
        name: counts.get(name, 0)
        for name in (
            "present_verified",
            "deleted_tombstoned",
            "unexplained_missing",
            "mismatched",
        )
    }
    return {
        "pass": bool(checksums)
        and not summary["unexplained_missing"]
        and not summary["mismatched"],
        "total": len(statuses),
        "counts": summary,
        "artifacts": statuses,
    }


def audit_result(result_dir: str | Path, *, output: str | Path | None = None) -> dict[str, Any]:
    """Audit a result without trusting a human-authored compliance judgment."""
    root = Path(result_dir).resolve()
    provenance = root / "provenance"
    try:
        config = (
            yaml.safe_load((provenance / "config.resolved.yaml").read_text(encoding="utf-8")) or {}
        )
    except (OSError, yaml.YAMLError):
        config = {}
    required_ids = {
        str(value)
        for value in config.get("provenance", {}).get("required_resource_identity_ids", [])
    }
    run = _json(provenance / "run_summary.json")
    source = {
        "pass": bool(run.get("git_commit"))
        and run.get("git_dirty") is False
        and bool(run.get("runtime_lock_id"))
        and run.get("runtime_lock_strict") is True,
        "git_commit": run.get("git_commit", ""),
        "git_dirty": run.get("git_dirty"),
        "runtime_lock_id": run.get("runtime_lock_id", ""),
        "runtime_lock_strict": run.get("runtime_lock_strict", False),
    }
    checks = {
        "run_status": {"pass": run.get("status") == "success", "status": run.get("status")},
        "source_identity": source,
        "tool_versions": _tool_check(provenance / "tool_versions.tsv"),
        "resource_identity": _resource_check(provenance / "resource_manifest.json", required_ids),
        "checksums": _checksum_check(root, provenance),
    }
    # Plugin-owned compliance checkpoints (P2-3): analysis-specific checks —
    # artifact layouts, preset names, preflight probes — live in the owning
    # plugin; the core audit only merges their results.
    # 插件自有合规检查点：分析专属检查属于所属插件，核心审计仅合并结果。
    analysis_type = str(run.get("analysis_type", "") or config.get("analysis_type", ""))
    if analysis_type:
        try:
            plugin = get_plugin(analysis_type)
        except ValueError:
            plugin = None
        if isinstance(plugin, ABIComplianceAuditPlugin):
            checks.update(plugin.compliance_checks(root, config))
    valid = all(bool(check.get("pass")) for check in checks.values())
    result = {"schema_version": "1.0", "result_dir": str(root), "valid": valid, "checks": checks}
    if output is not None:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return result
