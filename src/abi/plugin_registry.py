"""ABI plugin discovery, metadata, and lazy selected-plugin loading.

The plugin registry deliberately keeps discovery separate from implementation
imports. ``list_plugin_metadata`` reads the existing ``abi-plugin.yaml`` files
(and entry-point names when no manifest is available); ``get_plugin`` loads
only the selected entry point or source-tree builtin. ``list_plugins`` is
retained as an explicit, eager compatibility API for callers that need plugin
objects.
"""

from __future__ import annotations

import importlib
import warnings
from dataclasses import dataclass, replace
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple, cast

from abi.config import PLUGIN_ROOT, load_yaml
from abi.interfaces import ABIPlugin
from abi.plugin_validation import validate_plugin_class

ENTRY_POINT_GROUP = "abi.plugins"


class PluginSelectionError(RuntimeError):
    """Raised when a plugin cannot be selected unambiguously."""


class PluginLoadError(RuntimeError):
    """Raised when the selected plugin implementation cannot be loaded."""


@dataclass(frozen=True)
class PluginMetadata:
    """Small, implementation-free descriptor used by discovery consumers."""

    plugin_id: str
    display_name: str
    description: str
    report_title: str = ""
    entry_point: str = ""
    manifest_path: Optional[Path] = None
    metadata_available: bool = False
    metadata_error: Optional[str] = None
    status: str = "available"


@dataclass(frozen=True)
class _PluginRecord:
    metadata: PluginMetadata
    entry_points: Tuple[Any, ...] = ()
    manifest_targets: Tuple[str, ...] = ()
    manifest_errors: Tuple[str, ...] = ()


def _entry_points() -> Iterable[Any]:
    discovered = entry_points()
    if hasattr(discovered, "select"):
        return discovered.select(group=ENTRY_POINT_GROUP)
    return discovered.get(ENTRY_POINT_GROUP, ())  # type: ignore[attr-defined]


def _entry_point_value(entry_point: Any) -> str:
    value = getattr(entry_point, "value", None)
    return str(value) if value else ""


def _entry_point_sort_key(entry_point: Any) -> tuple[str, str, str]:
    distribution = getattr(entry_point, "dist", None)
    dist_name = str(getattr(distribution, "name", "")) if distribution else ""
    return (str(getattr(entry_point, "name", "")), _entry_point_value(entry_point), dist_name)


def _manifest_metadata(path: Path) -> PluginMetadata:
    """Read one manifest without importing the implementation it names."""

    try:
        manifest = load_yaml(path)
    except MemoryError:
        raise
    except Exception as exc:
        plugin_id = path.parent.name
        return PluginMetadata(
            plugin_id=plugin_id,
            display_name=plugin_id,
            description="",
            manifest_path=path,
            metadata_error=str(exc),
            status="metadata_error",
        )

    manifest_plugin_id = manifest.get("plugin_id")
    if not isinstance(manifest_plugin_id, str) or not manifest_plugin_id.strip():
        plugin_id = path.parent.name
    else:
        plugin_id = manifest_plugin_id
    display_name = manifest.get("display_name")
    description = manifest.get("description")
    report_title = manifest.get("report_title")
    entry_point = manifest.get("entry_point")
    valid = all(
        isinstance(value, str) and bool(value.strip())
        for value in (
            manifest.get("plugin_id"),
            display_name,
            description,
            report_title,
            entry_point,
        )
    )
    error = None if valid else "manifest metadata is incomplete"
    return PluginMetadata(
        plugin_id=plugin_id,
        display_name=str(display_name) if isinstance(display_name, str) else plugin_id,
        description=str(description) if isinstance(description, str) else "",
        report_title=str(report_title) if isinstance(report_title, str) else "",
        entry_point=str(entry_point) if isinstance(entry_point, str) else "",
        manifest_path=path,
        metadata_available=valid,
        metadata_error=error,
        status="available" if valid else "metadata_error",
    )


def _colocated_plugin_dirs() -> list[Path]:
    """Plugin data directories co-located with the ``abi.plugins`` package.

    WP11B: bundled plugin implementations ship their data (DAG, tool registry,
    limitations, …) inside their own package, so discovery works identically
    for source trees, editable installs, and per-plugin wheel installs.
    """

    base = Path(__file__).parent / "plugins"
    try:
        return sorted(path.parent for path in base.glob("*/abi-plugin.yaml"))
    except OSError as exc:
        warnings.warn(
            f"Unable to scan co-located ABI plugin packages: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return []


def plugin_data_roots(project_root: Path | None = None) -> dict[str, Path]:
    """Map ``plugin_id`` to its data root without loading any implementation.

    Two discovery sources are merged deterministically:

    1. Bundled plugin packages co-located under ``abi/plugins/<id>/`` (the
       WP11B distribution layout; also present in source/editable installs).
    2. Loose plugin directories under ``<project_root>/plugins/``
       (``PLUGIN_ROOT``), kept as the external/user-installed layout.

    A loose directory may not shadow a bundled plugin id: the bundled data
    root wins and the shadowed directory is reported, so data consumers never
    depend on enumeration order.
    """

    roots: dict[str, Path] = {path.name: path for path in _colocated_plugin_dirs()}
    # PLUGIN_ROOT is ``PROJECT_ROOT / "plugins"``; an explicit project root
    # keeps the same relative layout (used by tests and alternate checkouts).
    base = (Path(project_root) / "plugins") if project_root is not None else PLUGIN_ROOT
    try:
        loose = sorted(
            path
            for path in base.glob("*")
            if path.is_dir()
            and ((path / "abi-plugin.yaml").is_file() or (path / "tool_registry.yaml").is_file())
        )
    except OSError as exc:
        warnings.warn(
            f"Unable to scan loose ABI plugin directory {str(base)!r}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return roots
    for path in loose:
        if path.name in roots:
            warnings.warn(
                f"Loose ABI plugin directory shadows bundled plugin {path.name!r}: {path}",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        roots[path.name] = path
    return roots


def plugin_data_root(plugin_id: str, *, project_root: Path | None = None) -> Path | None:
    """Return the data root for *plugin_id*, or ``None`` when not discoverable."""

    return plugin_data_roots(project_root).get(str(plugin_id))


def _manifest_records() -> list[_PluginRecord]:
    records: list[_PluginRecord] = []
    try:
        # WP11B: bundled plugin manifests are co-located with each
        # implementation package; PLUGIN_ROOT remains a discovery path for
        # external/user-installed plugins.
        # WP11B：捆绑插件清单与实现包同址；PLUGIN_ROOT 保留为外部插件发现路径。
        manifest_paths = sorted(
            {
                *(directory / "abi-plugin.yaml" for directory in _colocated_plugin_dirs()),
                *PLUGIN_ROOT.glob("*/abi-plugin.yaml"),
            }
        )
    except MemoryError:
        raise
    except OSError as exc:
        warnings.warn(
            f"Unable to discover ABI plugin manifests: {exc}", RuntimeWarning, stacklevel=2
        )
        return records
    for path in manifest_paths:
        metadata = _manifest_metadata(path)
        records.append(
            _PluginRecord(
                metadata=metadata,
                manifest_targets=(metadata.entry_point,) if metadata.entry_point else (),
                manifest_errors=(metadata.metadata_error,) if metadata.metadata_error else (),
            )
        )
    return records


def _entry_point_records() -> list[_PluginRecord]:
    records: list[_PluginRecord] = []
    try:
        discovered = sorted(_entry_points(), key=_entry_point_sort_key)
    except MemoryError:
        raise
    except Exception as exc:
        warnings.warn(
            f"Unable to discover ABI plugin entry points: {exc}", RuntimeWarning, stacklevel=2
        )
        return records

    for entry_point in discovered:
        plugin_id = str(getattr(entry_point, "name", "")).strip()
        if not plugin_id:
            continue
        value = _entry_point_value(entry_point)
        records.append(
            _PluginRecord(
                metadata=PluginMetadata(
                    plugin_id=plugin_id,
                    display_name=plugin_id,
                    description="",
                    entry_point=value,
                    metadata_available=False,
                    status="metadata_unavailable",
                ),
                entry_points=(entry_point,),
            )
        )
    return records


def _records() -> dict[str, _PluginRecord]:
    """Merge manifest and entry-point records without importing implementations."""

    merged: dict[str, _PluginRecord] = {}
    for record in _manifest_records():
        plugin_id = record.metadata.plugin_id
        existing = merged.get(plugin_id)
        if existing is None:
            merged[plugin_id] = record
        else:
            merged[plugin_id] = _merge_record(existing, record)

    for record in _entry_point_records():
        plugin_id = record.metadata.plugin_id
        existing = merged.get(plugin_id)
        if existing is None:
            merged[plugin_id] = record
        else:
            merged[plugin_id] = _merge_record(existing, record)
    return merged


def _merge_record(left: _PluginRecord, right: _PluginRecord) -> _PluginRecord:
    """Merge one manifest and/or EP while preserving all competing EPs."""

    metadata = left.metadata
    if not metadata.metadata_available and right.metadata.metadata_available:
        metadata = right.metadata
    elif metadata.entry_point == "" and right.metadata.entry_point:
        metadata = replace(
            metadata,
            entry_point=right.metadata.entry_point,
            manifest_path=metadata.manifest_path or right.metadata.manifest_path,
        )
    eps = tuple(sorted(left.entry_points + right.entry_points, key=_entry_point_sort_key))
    manifest_targets = left.manifest_targets + right.manifest_targets
    manifest_errors = left.manifest_errors + right.manifest_errors
    if manifest_errors and metadata.metadata_error is None:
        metadata = replace(
            metadata,
            status="metadata_error",
            metadata_error="; ".join(manifest_errors),
        )
    return _PluginRecord(
        metadata=metadata,
        entry_points=eps,
        manifest_targets=manifest_targets,
        manifest_errors=manifest_errors,
    )


def _record_collisions(record: _PluginRecord) -> list[str]:
    """Return distinct implementation targets competing for one plugin id."""

    # A manifest and its one matching EP are the supported installed-package
    # duplicate. Multiple EP objects are competing registrations even when
    # their values happen to match: two distributions must not be selected by
    # enumeration order.
    targets: list[str] = []
    if len(record.manifest_targets) > 1:
        targets.extend(f"manifest:{target}" for target in record.manifest_targets)
    if len(record.entry_points) > 1:
        for entry_point in record.entry_points:
            distribution = getattr(entry_point, "dist", None)
            dist_name = str(getattr(distribution, "name", "")) if distribution else ""
            value = _entry_point_value(entry_point) or repr(entry_point)
            targets.append(f"{value} ({dist_name or 'unknown distribution'})")
    if len(record.manifest_targets) == 1 and len(record.entry_points) == 1:
        target = _entry_point_value(record.entry_points[0])
        if target != record.manifest_targets[0]:
            targets.extend(
                (f"manifest:{record.manifest_targets[0]}", target or repr(record.entry_points[0]))
            )
    return sorted(targets)


def _select_entry_point(record: _PluginRecord) -> Any | None:
    targets = _record_collisions(record)
    if targets:
        raise PluginSelectionError(
            f"ABI plugin {record.metadata.plugin_id!r} has competing implementations: "
            + ", ".join(repr(target) for target in targets)
        )
    if not record.entry_points:
        return None
    return record.entry_points[0]


def _load_target(target: str) -> type[Any]:
    module_name, separator, qualname = target.partition(":")
    if not separator or not module_name or not qualname:
        raise PluginLoadError(f"Invalid ABI plugin entry point {target!r}")
    module = importlib.import_module(module_name)
    implementation: Any = module
    for part in qualname.split("."):
        implementation = getattr(implementation, part)
    return implementation


def _instantiate(record: _PluginRecord) -> ABIPlugin:
    plugin_id = record.metadata.plugin_id
    source = record.metadata.entry_point or "unknown"
    try:
        if record.manifest_errors:
            raise PluginLoadError(
                f"ABI plugin {plugin_id!r} has invalid manifest metadata: "
                + "; ".join(record.manifest_errors)
            )
        entry_point = _select_entry_point(record)
        if entry_point is not None:
            plugin_class = entry_point.load()
            source = _entry_point_value(entry_point) or repr(entry_point)
        elif len(record.manifest_targets) == 1:
            plugin_class = _load_target(record.manifest_targets[0])
            source = record.manifest_targets[0]
        else:
            raise PluginLoadError(f"ABI plugin {plugin_id!r} has no implementation entry point")
        validate_plugin_class(plugin_class)
        plugin = cast(ABIPlugin, plugin_class())
    except MemoryError:
        raise
    except PluginSelectionError:
        raise
    except PluginLoadError:
        raise
    except Exception as exc:
        raise PluginLoadError(
            f"Failed to load ABI plugin {plugin_id!r} from {source!r}: {exc}"
        ) from exc

    actual_id = str(getattr(plugin, "plugin_id", ""))
    if actual_id != plugin_id:
        raise PluginLoadError(f"Loaded ABI plugin {plugin_id!r}: plugin_id is {actual_id!r}")
    return plugin


def list_plugin_metadata() -> List[PluginMetadata]:
    """Return sorted plugin identities without loading plugin implementations."""

    metadata: list[PluginMetadata] = []
    for _, record in sorted(_records().items()):
        collisions = _record_collisions(record)
        if collisions:
            metadata.append(
                replace(
                    record.metadata,
                    status="conflict",
                    metadata_error="competing implementations: " + ", ".join(collisions),
                )
            )
        else:
            metadata.append(record.metadata)
    return metadata


def get_plugin(plugin_id: str) -> ABIPlugin:
    """Load and return only the selected plugin implementation."""

    records = _records()
    record = records.get(plugin_id)
    if record is None:
        raise ValueError(f"Unknown ABI analysis type: {plugin_id}. Available: {sorted(records)}")
    return _instantiate(record)


def list_plugins() -> List[ABIPlugin]:
    """Eagerly load all plugins for the historical SDK compatibility API.

    New metadata-only callers should use :func:`list_plugin_metadata`.
    Failures remain isolated to the affected plugin, as in the former API.
    """

    plugins: list[ABIPlugin] = []
    records = _records()
    for plugin_id, record in sorted(records.items()):
        try:
            plugins.append(_instantiate(record))
        except MemoryError:
            raise
        except Exception as exc:
            warnings.warn(
                f"Skipping ABI plugin entry point {plugin_id!r}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
    return plugins


__all__ = [
    "ENTRY_POINT_GROUP",
    "PluginLoadError",
    "PluginMetadata",
    "PluginSelectionError",
    "get_plugin",
    "list_plugin_metadata",
    "list_plugins",
    "plugin_data_root",
    "plugin_data_roots",
]
