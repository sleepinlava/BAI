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
    "build_audit_snapshot",
    "write_audit_snapshot",
    "load_audit_snapshot",
]

AUDIT_SNAPSHOT_SCHEMA_VERSION = "abi.audit_snapshot.v1"
AUDIT_SNAPSHOT_FILENAME = "audit_snapshot.json"


def build_audit_snapshot(plugin: Any) -> Dict[str, Any]:
    """Build the audit snapshot mapping from a loaded plugin instance.

    Only declarations the plugin itself carries are captured: identity,
    report title, standard-table schemas, limitations, and citation/reference
    entries.  Nothing here depends on run outputs.
    """
    plugin_id = str(getattr(plugin, "plugin_id", ""))
    root = Path(str(getattr(plugin, "root", "")))

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
            schemas = {"_error": f"{type(exc).__name__}: {exc}"}

    limitations: list[str] = []
    limitations_path = root / "limitations.yaml" if str(root) else None
    if limitations_path is not None and limitations_path.exists():
        limitations = [str(item) for item in load_limitations(limitations_path)]

    references: Dict[str, Any] = {}
    citations_path = root / "citation_registry.yaml"
    if citations_path.is_file():
        try:
            data = load_yaml(citations_path)
            if isinstance(data, Mapping):
                references = dict(data)
        except Exception as exc:  # noqa: BLE001
            references = {"_error": f"{type(exc).__name__}: {exc}"}

    return {
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


def write_audit_snapshot(plugin: Any, provenance_dir: str | Path) -> Path:
    """Persist the audit snapshot for a run into *provenance_dir*.

    Best-effort by design: a snapshot failure is recorded inside the snapshot
    file (or skipped when even that is impossible) and must never abort the
    analysis run it audits.
    """
    directory = Path(provenance_dir)
    destination = directory / AUDIT_SNAPSHOT_FILENAME
    try:
        snapshot = build_audit_snapshot(plugin)
    except Exception as exc:  # noqa: BLE001
        snapshot = {
            "schema_version": AUDIT_SNAPSHOT_SCHEMA_VERSION,
            "analysis_type": str(getattr(plugin, "plugin_id", "")),
            "_error": f"snapshot build failed: {type(exc).__name__}: {exc}",
        }
    try:
        directory.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return destination
    return destination


def load_audit_snapshot(result_dir: str | Path) -> Dict[str, Any] | None:
    """Load a result directory's audit snapshot; ``None`` when absent/invalid.

    Old result directories predate snapshots; callers must report the missing
    snapshot instead of pretending full auditability (WP5: 旧记录缺字段时明确
    缺失，不伪造完整性).
    """
    path = Path(result_dir) / "provenance" / AUDIT_SNAPSHOT_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, Mapping):
        return None
    return dict(data)
