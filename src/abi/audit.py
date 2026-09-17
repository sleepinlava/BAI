"""Audit snapshot — plugin-independent facts captured at execution time.

WP5 (independent human audit interface): when a run writes new results it also
persists the audit-necessary metadata — standard-table schemas, declared
limitations, citation/reference entries, and plugin identity — into
``provenance/audit_snapshot.json``.  Basic structural checks and basic reports
read this snapshot, so a result directory stays auditable without the analysis
plugin, the plotting library, or the real tools installed.  Plugin-specific
parsing and scientific validation remain plugin work and report honestly
whether they ran.

审计快照 —— 执行时捕获的与插件无关的事实。生成新结果时一并保存审计必需的
schema、局限性、引用与插件身份；基础结构检查与基础报告读取该快照，使结果
目录在卸载分析插件、绘图库与真实工具后仍可审计。插件专有解析与科学校验
仍属插件，并如实报告是否执行。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping

from abi import __version__
from abi.config import load_yaml
from abi.report.limitations import load_limitations

__all__ = [
    "AUDIT_SNAPSHOT_SCHEMA_VERSION",
    "AUDIT_SNAPSHOT_FILENAME",
    "AuditSnapshotWriteError",
    "audit_snapshot_status",
    "build_audit_snapshot",
    "write_audit_snapshot",
    "load_audit_snapshot",
    "validate_audit_snapshot",
]

AUDIT_SNAPSHOT_SCHEMA_VERSION = "abi.audit_snapshot.v1"
AUDIT_SNAPSHOT_FILENAME = "audit_snapshot.json"


class AuditSnapshotWriteError(OSError):
    """Raised when the audit snapshot cannot be persisted."""


def build_audit_snapshot(plugin: Any) -> Dict[str, Any]:
    """Build the audit snapshot mapping from a loaded plugin instance.

    Only declarations the plugin itself carries are captured: identity,
    report title, standard-table schemas, limitations, and citation/reference
    entries.  Nothing here depends on run outputs.
    """
    plugin_id = str(getattr(plugin, "plugin_id", ""))
    root_value = str(getattr(plugin, "root", "") or "").strip()
    root = Path(root_value) if root_value else None
    snapshot_errors: list[str] = []

    schemas: Dict[str, Any] = {}
    table_schemas = getattr(plugin, "table_schemas", None)
    if callable(table_schemas):
        try:
            raw = table_schemas()
            if isinstance(raw, Mapping):
                schemas = {
                    str(name): [str(column) for column in columns] for name, columns in raw.items()
                }
        except Exception as exc:  # noqa: BLE001 — snapshot must never break a run
            snapshot_errors.append(
                f"standard_table_schemas could not be captured: {type(exc).__name__}: {exc}"
            )

    limitations: list[str] = []
    limitations_path = root / "limitations.yaml" if root is not None else None
    if limitations_path is not None and limitations_path.exists():
        try:
            limitations = [str(item) for item in load_limitations(limitations_path)]
        except Exception as exc:  # noqa: BLE001
            snapshot_errors.append(
                f"limitations could not be captured: {type(exc).__name__}: {exc}"
            )

    references: Dict[str, Any] = {}
    citations_path = root / "citation_registry.yaml" if root is not None else None
    if citations_path is not None and citations_path.is_file():
        try:
            data = load_yaml(citations_path)
            if isinstance(data, Mapping):
                references = dict(data)
        except Exception as exc:  # noqa: BLE001
            snapshot_errors.append(f"references could not be captured: {type(exc).__name__}: {exc}")

    snapshot: Dict[str, Any] = {
        "schema_version": AUDIT_SNAPSHOT_SCHEMA_VERSION,
        "analysis_type": plugin_id,
        "plugin_id": plugin_id,
        "report_title": str(getattr(plugin, "report_title", "") or ""),
        "standard_table_schemas": schemas,
        "limitations": limitations,
        "references": references,
        "abi_version": __version__,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
    }
    if snapshot_errors:
        snapshot["snapshot_errors"] = snapshot_errors
    return snapshot


def write_audit_snapshot(
    plugin: Any,
    provenance_dir: str | Path,
    *,
    strict: bool = False,
) -> Path:
    """Persist the audit snapshot for a run into *provenance_dir*.

    Declaration-capture failures are recorded in the snapshot so that a later
    validator can report an incomplete audit.  With ``strict=True``, filesystem
    failures are raised explicitly so a run cannot be reported as fully
    auditable when the artifact could not be persisted.  The default preserves
    the original best-effort helper contract for external callers; ABI runtime
    paths opt into strict handling.
    """
    directory = Path(provenance_dir)
    destination = directory / AUDIT_SNAPSHOT_FILENAME
    try:
        snapshot = build_audit_snapshot(plugin)
    except Exception as exc:  # noqa: BLE001
        snapshot = {
            "schema_version": AUDIT_SNAPSHOT_SCHEMA_VERSION,
            "analysis_type": str(getattr(plugin, "plugin_id", "")),
            "plugin_id": str(getattr(plugin, "plugin_id", "")),
            "standard_table_schemas": {},
            "limitations": [],
            "references": {},
            "abi_version": __version__,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "snapshot_errors": [f"snapshot build failed: {type(exc).__name__}: {exc}"],
        }
    try:
        directory.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as exc:
        if not strict:
            return destination
        raise AuditSnapshotWriteError(
            f"Failed to write audit snapshot {destination}: {exc}"
        ) from exc
    return destination


def load_audit_snapshot(result_dir: str | Path) -> Dict[str, Any] | None:
    """Load a valid result-directory audit snapshot.

    Old result directories predate snapshots; callers must report the missing
    snapshot instead of pretending full auditability (WP5: 旧记录缺字段时明确
    缺失，不伪造完整性).
    """
    status = audit_snapshot_status(result_dir)
    if status["status"] != "valid":
        return None
    snapshot = status.get("snapshot")
    return dict(snapshot) if isinstance(snapshot, Mapping) else None


def audit_snapshot_status(
    result_dir: str | Path,
    *,
    expected_analysis_type: str | None = None,
) -> Dict[str, Any]:
    """Return explicit missing, invalid, or valid snapshot status.

    When ``expected_analysis_type`` is supplied, the snapshot identity must
    agree with the result directory's plan identity before its declarations
    are trusted by plugin-independent validation or reporting.
    """
    path = Path(result_dir) / "provenance" / AUDIT_SNAPSHOT_FILENAME
    base: Dict[str, Any] = {
        "path": str(path),
        "status": "missing",
        "errors": ["Audit snapshot is missing"],
        "warnings": [],
        "snapshot": None,
    }
    if not path.is_file():
        return base
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        base["status"] = "invalid"
        base["errors"] = [f"Audit snapshot could not be read: {exc}"]
        return base
    if not isinstance(data, Mapping):
        base["status"] = "invalid"
        base["errors"] = ["Audit snapshot must contain a JSON object"]
        return base
    snapshot = dict(data)
    errors = validate_audit_snapshot(snapshot)
    if (
        not errors
        and expected_analysis_type
        and snapshot.get("analysis_type") != expected_analysis_type
    ):
        errors.append(
            "Audit snapshot analysis_type "
            f"{snapshot.get('analysis_type')!r} does not match result analysis_type "
            f"{expected_analysis_type!r}"
        )
    base["snapshot"] = snapshot
    base["errors"] = errors
    base["status"] = "invalid" if errors else "valid"
    optional_fields = (
        "plugin_id",
        "report_title",
        "references",
        "abi_version",
        "captured_at",
    )
    base["warnings"] = [
        f"Audit snapshot does not contain optional field: {field}"
        for field in optional_fields
        if field not in snapshot
    ]
    return base


def validate_audit_snapshot(snapshot: Any) -> list[str]:
    """Validate the stable structural contract of an audit snapshot."""
    if not isinstance(snapshot, Mapping):
        return ["Audit snapshot must contain a JSON object"]

    errors: list[str] = []
    if snapshot.get("schema_version") != AUDIT_SNAPSHOT_SCHEMA_VERSION:
        errors.append(f"Audit snapshot schema_version must be {AUDIT_SNAPSHOT_SCHEMA_VERSION!r}")
    for field in ("analysis_type", "standard_table_schemas", "limitations"):
        if field not in snapshot:
            errors.append(f"Audit snapshot missing required field: {field}")

    analysis_type = snapshot.get("analysis_type")
    if "analysis_type" in snapshot and not isinstance(analysis_type, str):
        errors.append("Audit snapshot analysis_type must be a string")

    schemas = snapshot.get("standard_table_schemas")
    if not isinstance(schemas, Mapping):
        errors.append("Audit snapshot standard_table_schemas must be an object")
    else:
        for table_name, columns in schemas.items():
            if not isinstance(table_name, str) or not isinstance(columns, list):
                errors.append(
                    "Audit snapshot standard_table_schemas entry "
                    f"{table_name!r} must contain a column list"
                )
                continue
            if not all(isinstance(column, str) for column in columns):
                errors.append(f"Audit snapshot columns for {table_name!r} must all be strings")

    limitations = snapshot.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(item, str) for item in limitations):
        errors.append("Audit snapshot limitations must be a list of strings")

    for field in ("plugin_id", "report_title", "abi_version", "captured_at"):
        if field in snapshot and not isinstance(snapshot[field], str):
            errors.append(f"Audit snapshot {field} must be a string")

    if (
        isinstance(snapshot.get("analysis_type"), str)
        and "plugin_id" in snapshot
        and isinstance(snapshot.get("plugin_id"), str)
        and snapshot["plugin_id"] != snapshot["analysis_type"]
    ):
        errors.append("Audit snapshot plugin_id must match analysis_type")

    if "references" in snapshot and not isinstance(snapshot["references"], Mapping):
        errors.append("Audit snapshot references must be an object")

    snapshot_errors = snapshot.get("snapshot_errors", [])
    if not isinstance(snapshot_errors, list) or not all(
        isinstance(item, str) for item in snapshot_errors
    ):
        errors.append("Audit snapshot snapshot_errors must be a list of strings")
    else:
        errors.extend(f"Audit snapshot capture error: {item}" for item in snapshot_errors)

    if "_error" in snapshot:
        errors.append(f"Audit snapshot capture error: {snapshot['_error']}")
    return errors
