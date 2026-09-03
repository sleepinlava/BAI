"""ABI resource checking and setup orchestration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from abi import resource_downloader as _resource_downloader
from abi.errors import ABIError
from abi.interfaces import ABIResourcePlugin
from abi.plugins import get_plugin
from abi.resource_downloader import DownloadResult, DownloadSpec, ResourceDownloader
from abi.timeouts import DEFAULT_RESOURCE_TIMEOUT_SECONDS, timeout_from_env_or_value

__path__ = []  # type: ignore[var-annotated]
sys.modules.setdefault(__name__ + ".downloader", _resource_downloader)
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
    """Prepare or plan resources for an ABI analysis type."""
    plugin = get_plugin(analysis_type)
    if isinstance(plugin, ABIResourcePlugin):
        rows = plugin.setup_resources(
            config,
            resource_ids=resource_ids,
            dry_run=dry_run,
            mock=mock,
        )
        return mark_mock_mode(rows, mock=mock)
    if not dry_run and not mock:
        raise ABIError(
            f"Resource setup is not implemented for analysis type {analysis_type!r}. "
            "Use --dry-run to inspect the resource plan or configure paths manually."
        )
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
    downloader = ResourceDownloader(Path(), dry_run=dry_run, mock=mock)
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
            downloader._mock_resource(DownloadSpec(resource_id=str(current["resource_id"])), target)
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
    the user must pick an organism/genome build. Mock mode uses
    ResourceDownloader for consistent mock resource creation.
    """
    selected = set(resource_ids or [])
    downloader = ResourceDownloader(Path(), dry_run=dry_run, mock=mock)
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
                downloader._mock_resource(DownloadSpec(resource_id=resource_id), target)
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
