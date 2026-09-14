"""ABI resource checking and setup orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from abi.errors import ABIError
from abi.interfaces import ABIResourcePlugin, ABIResourceSetupPlugin
from abi.plugin_registry import get_plugin
from abi.timeouts import DEFAULT_RESOURCE_TIMEOUT_SECONDS, timeout_from_env_or_value

__all__ = [
    "apply_resource_overrides",
    "check_generic_resources",
    "check_resources",
    "configured_or_default_resource_path",
    "download_result_to_row",
    "mark_mock_mode",
    "resource_timeout",
    "setup_manual_resource_bundle",
    "setup_reference_resources",
    "setup_resources",
]
_PLACEHOLDER_MARKERS = ("NOT_CONFIGURED", "TODO", "PLACEHOLDER")

ABIR_RESOURCE_SENTINEL = ".abi_resource.json"


@dataclass
class DownloadResult:
    """Resource preparation result row (WP8: no downloads — planning/mock/report)."""

    resource_id: str
    path: Path
    status: str  # ok | missing | manual_required | error | skipped | planned
    version: str = ""
    checksum: str = ""
    file_count: int = 0
    size_bytes: int = 0
    downloaded_at: str = ""
    message: str = ""
    command: list[str] = field(default_factory=list)


def write_mock_resource(dest: Path, resource_id: str) -> None:
    """Fabricate a mock resource directory with a ready sentinel (tests only).

    Replaces the retired downloader's mock fabrication: an empty directory plus
    a ``.abi_resource.json`` sentinel marking the resource as fixture data.
    生成 mock 资源目录与就绪哨兵（仅测试用）：空目录 + ``.abi_resource.json``
    哨兵，标记该资源为夹具数据。
    """
    dest.mkdir(parents=True, exist_ok=True)
    sentinel = dest / ABIR_RESOURCE_SENTINEL
    if not sentinel.exists():
        sentinel.write_text(
            json.dumps(
                {"resource_id": resource_id, "kind": "mock", "note": "test fixture only"},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


def resource_timeout(config: Mapping[str, Any]) -> float | None:
    execution = config.get("execution", {})
    configured = (
        execution.get("resource_timeout_seconds") if isinstance(execution, Mapping) else None
    )
    return timeout_from_env_or_value(
        "ABI_RESOURCE_TIMEOUT_SECONDS",
        configured,
        default=DEFAULT_RESOURCE_TIMEOUT_SECONDS,
    )


def check_resources(
    *,
    analysis_type: str,
    config: Mapping[str, Any],
    resource_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Check configured resources for an ABI analysis type."""
    plugin = get_plugin(analysis_type)
    if isinstance(plugin, ABIResourcePlugin):
        return plugin.check_resources(config, resource_ids=resource_ids)
    return check_generic_resources(analysis_type, config, resource_ids=resource_ids)


def setup_resources(
    *,
    analysis_type: str,
    config: Mapping[str, Any],
    resource_ids: Optional[Sequence[str]] = None,
    dry_run: bool = False,
    mock: bool = False,
) -> List[Dict[str, Any]]:
    """Plan, fabricate fixtures for, or report resource requirements (WP8).

    ABI never downloads or installs: real-run returns explicit
    ``manual_required`` guidance rows, ``dry_run`` reports the preparation
    plan, and ``mock`` fabricates fixture directories for tests.
    ABI 绝不下载或安装：真实运行返回明确的 manual_required 指引行，dry_run
    输出准备计划，mock 为测试生成夹具目录。
    """
    plugin = get_plugin(analysis_type)
    if isinstance(plugin, ABIResourceSetupPlugin):
        rows = plugin.setup_resources(
            config,
            resource_ids=resource_ids,
            dry_run=dry_run,
            mock=mock,
        )
        return mark_mock_mode(rows, mock=mock)
    rows = check_generic_resources(analysis_type, config, resource_ids=resource_ids)
    planned = []
    for row in rows:
        planned_row = dict(row)
        planned_row["mock"] = mock
        if dry_run:
            planned_row["status"] = "planned"
            planned_row["message"] = "No downloader is registered; configure this path manually."
        elif mock:
            path = Path(str(row["path"]))
            path.mkdir(parents=True, exist_ok=True)
            (path / ".abi_mock_resource").write_text(
                f"{analysis_type}:{row['resource_id']}\n",
                encoding="utf-8",
            )
            planned_row["status"] = "ok"
            planned_row["message"] = "Mock resource directory prepared."
        elif planned_row["status"] != "ok":
            # WP8 real-run: report manual requirements with guidance — ABI
            # never downloads or installs.
            # WP8 真实运行：报告 manual_required 指引——ABI 绝不下载或安装。
            planned_row["status"] = "manual_required"
            planned_row["message"] = (
                "Provision the upstream database/environment bundle, then set "
                f"resources.{row['resource_id']} to its validated path."
            )
        planned.append(planned_row)
    return planned


def mark_mock_mode(rows: Sequence[Mapping[str, Any]], *, mock: bool) -> List[Dict[str, Any]]:
    """Return resource setup rows with an explicit mock-mode marker."""
    return [dict(row, mock=mock) for row in rows]


def setup_manual_resource_bundle(
    analysis_type: str,
    config: Mapping[str, Any],
    *,
    resource_ids: Optional[Sequence[str]],
    dry_run: bool,
    mock: bool,
) -> List[Dict[str, Any]]:
    """Prepare mock bundles or report explicit manual setup requirements.

    These plugins depend on organism/site-specific databases or an upstream
    multi-environment installation. Automatically choosing or partially
    downloading such resources would create a misleading runnable state.
    """
    rows = check_generic_resources(analysis_type, config, resource_ids=resource_ids)
    planned: List[Dict[str, Any]] = []
    for row in rows:
        current = dict(row)
        current["mock"] = mock
        target = configured_or_default_resource_path(config, str(current["resource_id"]))
        current["path"] = str(target)
        if dry_run:
            current["status"] = "planned"
            current["message"] = (
                "Would prepare a mock resource directory for smoke testing."
                if mock
                else "Would verify this manually provisioned resource; no implicit "
                "database or environment selection is performed."
            )
        elif current["status"] == "ok":
            current["message"] = "Configured resource exists."
        elif mock:
            write_mock_resource(target, str(current["resource_id"]))
            current["status"] = "ok"
            current["message"] = "Mock resource directory prepared."
        else:
            current["status"] = "manual_required"
            current["message"] = (
                "Provision the upstream database/environment bundle, then set "
                f"resources.{current['resource_id']} to its validated path."
            )
        current.setdefault("command", [])
        current.setdefault("ready_check", "non_empty_directory")
        current.setdefault("source_url", "")
        current.setdefault("version", "")
        current.setdefault("checksum", "")
        planned.append(current)
    return planned


def configured_or_default_resource_path(config: Mapping[str, Any], resource_id: str) -> Path:
    resources = config.get("resources", {})
    value = resources.get(resource_id) if isinstance(resources, Mapping) else None
    if isinstance(value, Mapping):
        value = value.get("path")
    if value and not _is_placeholder_resource_value(value):
        return Path(str(value))
    return Path(str(config.get("outdir", "results"))) / "resources" / resource_id


def _is_placeholder_resource_value(value: Any) -> bool:
    text = str(value).strip()
    upper = text.upper()
    if any(marker in upper for marker in _PLACEHOLDER_MARKERS):
        return True
    normalized = text.replace("\\", "/").lower()
    return normalized.startswith(("/path/to/", "path/to/", "/your/path/", "your/path/"))


def setup_reference_resources(
    analysis_type: str,
    config: Mapping[str, Any],
    *,
    resource_ids: Optional[Sequence[str]],
    dry_run: bool,
    mock: bool,
) -> List[Dict[str, Any]]:
    """Plan or mock organism-specific reference resources.

    Genome indices and annotations cannot be downloaded automatically ---
    the user must pick an organism/genome build (WP8: no downloads).
    """
    selected = set(resource_ids or [])
    rows: List[Dict[str, Any]] = []
    for resource_id in ("genome_index", "annotation_gtf"):
        if selected and resource_id not in selected:
            continue
        target = configured_or_default_resource_path(config, resource_id)
        if dry_run:
            status = "planned"
            message = (
                "Would prepare a mock reference resource for smoke testing."
                if mock
                else "Select an organism/genome build and configure this reference path."
            )
        elif mock:
            if resource_id == "genome_index":
                write_mock_resource(target, resource_id)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    'chrMock\tABI\tgene\t1\t4\t.\t+\t.\tgene_id "MOCK1";\n',
                    encoding="utf-8",
                )
            status = "ok"
            message = "Mock reference resource prepared."
        elif target.exists():
            status = "ok"
            message = "Configured reference resource exists."
        else:
            status = "manual_required"
            message = (
                "Automatic download requires an organism/genome build choice; "
                "configure the reference path explicitly."
            )
        rows.append(
            {
                "resource_id": resource_id,
                "tool_id": "star" if resource_id == "genome_index" else "featurecounts",
                "field": resource_id,
                "path": str(target),
                "status": status,
                "version": "",
                "source_url": "",
                "checksum": "",
                "command": [],
                "ready_check": "path_exists",
                "directory_file_count": _directory_file_count(target),
                "directory_size_bytes": 0,
                "message": message,
                "mock": mock,
            }
        )
    return rows


def check_generic_resources(
    analysis_type: str,
    config: Mapping[str, Any],
    *,
    resource_ids: Optional[Sequence[str]],
) -> List[Dict[str, Any]]:
    get_plugin(analysis_type)
    resources = config.get("resources", {})
    if not isinstance(resources, Mapping):
        return []
    selected = set(resource_ids or [])
    rows = []
    for key, value in sorted(resources.items()):
        if key == "root":
            continue
        if selected and key not in selected:
            continue
        if isinstance(value, Mapping):
            path_value = value.get("path") or value.get("database") or value.get("directory")
        else:
            path_value = value
        path = Path(str(path_value or ""))
        status = _generic_resource_status(path_value)
        rows.append(
            {
                "resource_id": str(key),
                "tool_id": "",
                "field": str(key),
                "path": str(path),
                "status": status,
                "version": "",
                "source_url": "",
                "checksum": "",
                "command": [],
                "ready_check": "path_exists",
                "directory_file_count": (_directory_file_count(path) if status == "ok" else 0),
                "directory_size_bytes": 0,
                "message": _generic_resource_message(status),
            }
        )
    return rows


def _generic_resource_status(value: Any) -> str:
    if value is None or value == "":
        return "not_configured"
    text = str(value)
    if any(marker in text for marker in _PLACEHOLDER_MARKERS):
        return "not_configured"
    path = Path(text)
    if not path.exists():
        return "missing"
    if path.is_dir() and not any(path.iterdir()):
        return "incomplete"
    return "ok"


def _generic_resource_message(status: str) -> str:
    if status == "ok":
        return "Configured resource path exists."
    if status == "missing":
        return "Configured resource path does not exist."
    if status == "incomplete":
        return "Configured resource directory is empty; database setup may be incomplete."
    return "Resource path is not configured."


def _directory_file_count(path: Path) -> int:
    if path.is_file():
        return 1
    if not path.is_dir():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file())


def download_result_to_row(
    result: DownloadResult,
    *,
    tool_id: str = "",
    field: str = "",
    source_url: str = "",
    ready_check: str = "sentinel",
    mock: bool = False,
) -> dict[str, Any]:
    """Convert a DownloadResult to the resource row dict format."""
    file_count = result.file_count or (
        sum(1 for _ in result.path.rglob("*") if _.is_file()) if result.path.is_dir() else 0
    )
    size_bytes = result.size_bytes or (
        sum(f.stat().st_size for f in result.path.rglob("*") if f.is_file())
        if result.path.is_dir()
        else 0
    )
    return {
        "resource_id": result.resource_id,
        "tool_id": tool_id,
        "field": field or result.resource_id,
        "path": str(result.path),
        "status": result.status,
        "version": result.version,
        "source_url": source_url,
        "checksum": result.checksum,
        "command": list(result.command),
        "ready_check": ready_check,
        "directory_file_count": file_count,
        "directory_size_bytes": size_bytes,
        "message": result.message,
        "mock": mock,
    }


def apply_resource_overrides(config: Dict[str, Any], overrides: Sequence[str]) -> None:
    """Apply ``--resource id=path`` overrides to a config dict in-place.

    Handles ``id=path`` syntax: sets ``config.resources.<id>`` to ``<path>``.
    For the full ``id:field=path`` syntax, use the plugin's version directly.
    """
    resources = config.setdefault("resources", {})
    if not isinstance(resources, Mapping):
        resources = {}
        config["resources"] = resources
    for item in overrides:
        key, _, path = item.partition("=")
        key = key.strip()
        path = path.strip()
        if not key or not path:
            raise ABIError(f"Invalid --resource override (expected id=path): {item!r}")
        resource_id = key
        block = resources.setdefault(resource_id, {})
        if not isinstance(block, dict):
            block = {}
            resources[resource_id] = block
        block["path"] = path
