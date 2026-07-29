"""Linux runtime discovery for ABI-managed environments and external tools.

This module is the transport-neutral source of truth for locating a Mamba root,
named environment prefixes, executables, and Python interpreters.  Every
resolution includes its source so diagnostics and provenance can explain why a
path was selected.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from abi.config import PROJECT_ROOT


class RuntimeEnvironmentError(RuntimeError):
    """Raised when explicit runtime configuration cannot be honored."""


DEFAULT_ENVIRONMENT_SOLVER_TIMEOUT_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class PathResolution:
    """A resolved filesystem path and the rule that selected it."""

    path: Path | None
    source: str

    @property
    def exists(self) -> bool:
        return self.path is not None and self.path.exists()

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path) if self.path is not None else None,
            "source": self.source,
            "exists": self.exists,
        }


@dataclass(frozen=True)
class MambaRootResolution(PathResolution):
    """Resolved Mamba root plus solver information and known environment prefixes."""

    solver: str | None = None
    known_prefixes: tuple[Path, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "solver": self.solver,
                "known_prefixes": [str(path) for path in self.known_prefixes],
            }
        )
        return payload


@dataclass(frozen=True)
class EnvironmentPrefixResolution(PathResolution):
    """Environment prefix whose existence requires Conda environment markers."""

    @property
    def exists(self) -> bool:
        return self.path is not None and _is_environment_prefix(self.path)


def discover_mamba_root(
    explicit_root: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    probe_solver: bool = True,
) -> MambaRootResolution:
    """Discover the Linux Mamba root using a deterministic precedence order.

    Explicit CLI/API configuration and environment overrides are authoritative:
    if they point to a missing path, discovery fails instead of silently
    selecting another installation.
    """

    env = dict(os.environ if environ is None else environ)
    project = Path(project_root or PROJECT_ROOT).expanduser()
    user_home = Path(home or env.get("HOME") or Path.home()).expanduser()

    if explicit_root is not None:
        return _authoritative_root(explicit_root, source="explicit")

    for variable, source in (
        ("ABI_MAMBA_ROOT", "ABI_MAMBA_ROOT"),
        ("MAMBA_ROOT_PREFIX", "MAMBA_ROOT_PREFIX"),
        ("AUTOPLASM_MAMBA_ROOT", "AUTOPLASM_MAMBA_ROOT"),
    ):
        value = env.get(variable)
        if value:
            return _authoritative_root(value, source=source)

    compatibility = (
        project / ".mamba",
        project.parent / ".mamba",
        project.parent / "abi-envs",
    )
    populated = [
        candidate for candidate in compatibility if _environment_prefix_count(candidate) > 0
    ]
    if populated:
        selected = max(
            populated,
            key=lambda path: (_environment_prefix_count(path), -compatibility.index(path)),
        )
        return MambaRootResolution(selected.resolve(), "repository-compatibility")

    user_root = _linux_user_mamba_root(env, user_home)
    if _environment_prefix_count(user_root) > 0:
        return MambaRootResolution(user_root.resolve(), "linux-user-data")

    solver_resolution = _discover_solver_root(env, probe=probe_solver)
    if solver_resolution is not None:
        return solver_resolution

    if user_root.exists():
        return MambaRootResolution(user_root.resolve(), "linux-user-data")

    return MambaRootResolution(user_root.resolve(), "linux-user-data-default")


def resolved_mamba_root(
    explicit_root: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    project_root: Path | None = None,
) -> Path:
    """Return only the selected Mamba root for compatibility callers."""

    resolution = discover_mamba_root(
        explicit_root,
        environ=environ,
        project_root=project_root,
        probe_solver=False,
    )
    assert resolution.path is not None
    return resolution.path


def resolve_environment_prefix(
    mamba_root: Path,
    env_name: str,
    *,
    explicit_prefix: str | Path | None = None,
    known_prefixes: Sequence[Path] = (),
) -> EnvironmentPrefixResolution:
    """Resolve a named environment prefix and report the selected layout."""

    if explicit_prefix is not None:
        prefix = Path(explicit_prefix).expanduser()
        if not prefix.exists():
            raise RuntimeEnvironmentError(f"Explicit environment prefix does not exist: {prefix}")
        return EnvironmentPrefixResolution(prefix.resolve(), "explicit-prefix")

    root = Path(mamba_root).expanduser()
    managed = root / "envs" / env_name
    if _is_environment_prefix(managed):
        return EnvironmentPrefixResolution(managed.resolve(), "managed-environment")

    direct = root / env_name
    if _is_environment_prefix(direct):
        return EnvironmentPrefixResolution(direct.resolve(), "direct-environment")

    for raw_prefix in known_prefixes:
        prefix = Path(raw_prefix).expanduser()
        if prefix.name == env_name and _is_environment_prefix(prefix):
            return EnvironmentPrefixResolution(prefix.resolve(), "solver-prefix")

    return EnvironmentPrefixResolution(managed.resolve(), "managed-environment-default")


def resolve_executable(
    executable: str,
    *,
    env_prefix: Path | None = None,
    extra_dirs: Sequence[Path] = (),
    environ: Mapping[str, str] | None = None,
    allow_system: bool = True,
) -> PathResolution:
    """Resolve an executable by explicit, environment, resource, then PATH order."""

    env = dict(os.environ if environ is None else environ)
    requested = Path(executable).expanduser()
    if requested.is_absolute() or requested.parent != Path("."):
        if requested.is_file() and os.access(requested, os.X_OK):
            return PathResolution(requested.resolve(), "explicit-executable")
        if requested.is_file():
            return PathResolution(None, "non-executable-explicit-executable")
        return PathResolution(None, "missing-explicit-executable")

    if env_prefix is not None:
        found = shutil.which(executable, path=str(Path(env_prefix) / "bin"))
        if found:
            return PathResolution(Path(found).resolve(), "environment")

    for directory in extra_dirs:
        found = shutil.which(executable, path=str(directory))
        if found:
            return PathResolution(Path(found).resolve(), "resource-path")

    if allow_system:
        found = shutil.which(executable, path=env.get("PATH", ""))
        if found:
            return PathResolution(Path(found).resolve(), "system-path")

    return PathResolution(None, "missing")


def resolve_python(
    *,
    env_prefix: Path | None = None,
    internal: bool = False,
    environ: Mapping[str, str] | None = None,
    allow_system: bool = True,
) -> PathResolution:
    """Resolve the correct Python interpreter for ABI or an assigned environment."""

    if internal:
        return PathResolution(Path(sys.executable).resolve(), "abi-python")

    if env_prefix is not None:
        resolved = resolve_executable(
            "python",
            env_prefix=env_prefix,
            environ=environ,
            allow_system=False,
        )
        if resolved.path is not None:
            return resolved

    if allow_system:
        for name in ("python3", "python"):
            resolved = resolve_executable(name, environ=environ)
            if resolved.path is not None:
                return resolved
    return PathResolution(None, "missing")


def build_environment_report(
    *,
    explicit_root: str | Path | None = None,
    tool_names: Sequence[str] = (),
    analysis_type: str | None = None,
    environ: Mapping[str, str] | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Build a machine-readable Linux environment discovery and health report."""

    env = dict(os.environ if environ is None else environ)
    root = discover_mamba_root(
        explicit_root,
        environ=env,
        project_root=project_root,
        home=home,
    )
    assert root.path is not None
    manifest = load_environment_assignments()
    environments = manifest.get("environments", {})
    if not isinstance(environments, Mapping):
        environments = {}

    environment_rows: list[dict[str, Any]] = []
    prefixes: dict[str, Path] = {}
    for env_name in sorted(str(name) for name in environments):
        prefix = resolve_environment_prefix(
            root.path,
            env_name,
            known_prefixes=root.known_prefixes,
        )
        assert prefix.path is not None
        prefixes[env_name] = prefix.path
        python = (
            resolve_python(
                env_prefix=prefix.path,
                environ=env,
                allow_system=False,
            )
            if prefix.exists
            else PathResolution(None, "environment-missing")
        )
        environment_rows.append(
            {
                "name": env_name,
                "prefix": str(prefix.path),
                "source": prefix.source,
                "exists": prefix.exists,
                "python": python.to_dict(),
            }
        )

    raw_assignments = manifest.get("tool_assignments", {})
    assignments = _flatten_tool_assignments(raw_assignments)
    plugin_assignments: Mapping[str, Any] = {}
    plugin_tools: dict[str, Mapping[str, Any]] = {}
    if analysis_type and isinstance(raw_assignments, Mapping):
        candidate = raw_assignments.get(analysis_type, {})
        if isinstance(candidate, Mapping):
            plugin_assignments = candidate
            assignments.update(
                {
                    str(tool_name): str(env_name)
                    for tool_name, env_name in plugin_assignments.items()
                }
            )
        plugin_tools = _load_plugin_tool_metadata(analysis_type)
    requested_tools = list(dict.fromkeys(str(name) for name in tool_names))
    if analysis_type and not requested_tools:
        requested_tools = sorted(str(name) for name in plugin_assignments)
    tool_rows: list[dict[str, Any]] = []
    report_project_root = Path(project_root or PROJECT_ROOT).expanduser()
    for requested_tool in requested_tools:
        tool_id, metadata = _match_plugin_tool(requested_tool, plugin_tools)
        executable = str(metadata.get("executable") or tool_id)
        assigned_env_name = assignments.get(tool_id)
        assigned_prefix = prefixes.get(assigned_env_name) if assigned_env_name else None
        extra_dirs = _registry_extra_path_dirs(
            metadata,
            env_prefix=assigned_prefix,
            environ=env,
            project_root=report_project_root,
        )
        resolved = resolve_executable(
            executable,
            env_prefix=assigned_prefix,
            extra_dirs=extra_dirs,
            environ=env,
        )
        tool_rows.append(
            {
                "tool": requested_tool,
                "tool_id": tool_id,
                "executable": executable,
                "environment": assigned_env_name,
                **resolved.to_dict(),
            }
        )

    system = platform.system()
    architecture = _normalized_architecture(platform.machine())
    issues: list[str] = []
    if system != "Linux":
        issues.append(f"unsupported_platform:{system}")
    missing_tools = [row["tool_id"] for row in tool_rows if not row["exists"]]
    issues.extend(f"missing_tool:{name}" for name in missing_tools)

    plugin_status: dict[str, Any] | None = None
    if analysis_type:
        support = manifest.get("platform_support", {})
        plugin_matrix = support.get("plugins", {}) if isinstance(support, Mapping) else {}
        statuses = (
            plugin_matrix.get(analysis_type, {}) if isinstance(plugin_matrix, Mapping) else {}
        )
        status = (
            statuses.get(architecture, "not_declared")
            if isinstance(statuses, Mapping)
            else "not_declared"
        )
        plugin_status = {
            "analysis_type": analysis_type,
            "architecture": architecture,
            "status": status,
        }
        if str(status).startswith("unsupported"):
            issues.append(f"unsupported_plugin:{analysis_type}:{architecture}")
        if analysis_type not in raw_assignments:
            issues.append(f"unknown_plugin:{analysis_type}")

    return {
        "platform": {
            "system": system,
            "architecture": platform.machine(),
            "normalized_architecture": architecture,
            "python": str(Path(sys.executable).resolve()),
        },
        "mamba_root": root.to_dict(),
        "support": manifest.get("platform_support", {}),
        "plugin": plugin_status,
        "environments": environment_rows,
        "tools": tool_rows,
        "issues": issues,
        "healthy": not issues,
    }


def manage_environments(
    *,
    action: str,
    environment_names: Sequence[str],
    analysis_type: str | None = None,
    solver: str | Path | None = None,
    explicit_root: str | Path | None = None,
    dry_run: bool = False,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Create or update ABI-managed Linux environments with an auditable solver call."""

    if action not in {"install", "update"}:
        raise RuntimeEnvironmentError(f"Unsupported environment action: {action}")
    if platform.system() != "Linux":
        raise RuntimeEnvironmentError(
            f"ABI managed environments support Linux only, not {platform.system()}"
        )

    env = dict(os.environ if environ is None else environ)
    selected = _select_environment_names(
        environment_names,
        analysis_type=analysis_type,
    )
    root, root_source = _resolve_write_root(
        explicit_root,
        environ=env,
        home=home,
    )
    solver_report = _resolve_environment_solver(solver, environ=env)

    results: list[dict[str, Any]] = []
    for env_name in selected:
        spec_bytes = _render_environment_spec(env_name)
        spec_hash = hashlib.sha256(spec_bytes).hexdigest()
        prefix = (root / "envs" / env_name).resolve()
        spec_path = (root / "specs" / f"{env_name}.yml").resolve()
        existing_spec = spec_path.read_bytes() if spec_path.is_file() else None
        spec_state = (
            "missing"
            if existing_spec is None
            else ("matches" if existing_spec == spec_bytes else "differs")
        )
        command = _environment_solver_command(
            solver_report["name"],
            solver_report["executable"],
            action=action,
            prefix=prefix,
            spec_path=spec_path,
        )

        already_installed = _is_environment_prefix(prefix)
        executed = False
        if action == "install" and already_installed:
            status = "unchanged"
        elif dry_run:
            status = f"planned_{'create' if action == 'install' else 'update'}"
        else:
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            previous_spec = existing_spec
            try:
                _write_bytes_atomic(spec_path, spec_bytes)
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=DEFAULT_ENVIRONMENT_SOLVER_TIMEOUT_SECONDS,
                    env=_solver_process_environment(env, root),
                )
                if completed.returncode != 0:
                    detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
                    raise RuntimeEnvironmentError(
                        f"{solver_report['name']} {action} failed for {env_name}: {detail}"
                    )
                if not _is_environment_prefix(prefix):
                    raise RuntimeEnvironmentError(
                        f"{solver_report['name']} reported success "
                        f"but no environment exists: {prefix}"
                    )
            except BaseException:
                if previous_spec is None:
                    spec_path.unlink(missing_ok=True)
                else:
                    _write_bytes_atomic(spec_path, previous_spec)
                raise
            status = "updated" if already_installed else "created"
            executed = True
            spec_state = "matches"

        results.append(
            {
                "name": env_name,
                "status": status,
                "executed": executed,
                "prefix": str(prefix),
                "spec_path": str(spec_path),
                "spec_sha256": spec_hash,
                "spec_state": spec_state,
                "command": command,
            }
        )

    return {
        "action": action,
        "dry_run": dry_run,
        "mamba_root": {"path": str(root), "source": root_source},
        "solver": solver_report,
        "analysis_type": analysis_type,
        "environments": results,
        "healthy": True,
    }


def load_environment_assignments() -> Mapping[str, Any]:
    """Load the packaged environment manifest, with a checkout fallback."""

    import yaml

    try:
        from importlib.resources import files

        data = files("abi.data").joinpath("environments.yaml")
        if data.is_file():
            return yaml.safe_load(data.read_bytes()) or {}
    except Exception:
        pass

    dev_path = PROJECT_ROOT / "environments.yaml"
    if dev_path.exists():
        return yaml.safe_load(dev_path.read_bytes()) or {}

    raise FileNotFoundError(
        "environments.yaml not found in package data or project root. "
        "Rebuild the wheel or re-run from the project root."
    )


def _authoritative_root(value: str | Path, *, source: str) -> MambaRootResolution:
    path = Path(value).expanduser()
    if not path.exists():
        raise RuntimeEnvironmentError(f"{source} Mamba root does not exist: {path}")
    if not path.is_dir():
        raise RuntimeEnvironmentError(f"{source} Mamba root is not a directory: {path}")
    return MambaRootResolution(path.resolve(), source)


def _resolve_write_root(
    explicit_root: str | Path | None,
    *,
    environ: Mapping[str, str],
    home: Path | None,
) -> tuple[Path, str]:
    if explicit_root is not None:
        return _validated_write_root(explicit_root, source="explicit")
    for variable in ("ABI_MAMBA_ROOT", "MAMBA_ROOT_PREFIX", "AUTOPLASM_MAMBA_ROOT"):
        value = environ.get(variable)
        if value:
            return _validated_write_root(value, source=variable)
    user_home = Path(home or environ.get("HOME") or Path.home()).expanduser()
    return _validated_write_root(
        _linux_user_mamba_root(environ, user_home),
        source="linux-user-data-write",
    )


def _validated_write_root(value: str | Path, *, source: str) -> tuple[Path, str]:
    path = Path(value).expanduser()
    if path.exists() and not path.is_dir():
        raise RuntimeEnvironmentError(f"{source} Mamba root is not a directory: {path}")
    return path.resolve(), source


def _resolve_environment_solver(
    explicit_solver: str | Path | None,
    *,
    environ: Mapping[str, str],
) -> dict[str, str]:
    requested = explicit_solver or environ.get("ABI_ENV_SOLVER")
    source = "explicit" if explicit_solver is not None else "ABI_ENV_SOLVER"
    candidates = [str(requested)] if requested else ["micromamba", "mamba", "conda"]
    if requested is None:
        source = "auto"

    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_absolute() or path.parent != Path("."):
            executable = (
                str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
            )
        else:
            executable = shutil.which(candidate, path=environ.get("PATH", ""))
        if executable is None:
            continue
        name = Path(executable).name
        if name not in {"micromamba", "mamba", "conda"}:
            raise RuntimeEnvironmentError(f"Unsupported environment solver executable name: {name}")
        completed = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=_solver_process_environment(environ, None),
        )
        if completed.returncode != 0:
            raise RuntimeEnvironmentError(f"Unable to query environment solver: {executable}")
        version = completed.stdout.strip() or completed.stderr.strip()
        if not version:
            raise RuntimeEnvironmentError(f"Environment solver returned no version: {executable}")
        return {
            "name": name,
            "executable": str(Path(executable).resolve()),
            "version": version,
            "source": source,
        }

    label = str(requested) if requested is not None else "micromamba, mamba, or conda"
    raise RuntimeEnvironmentError(f"No supported environment solver found: {label}")


def _select_environment_names(
    environment_names: Sequence[str],
    *,
    analysis_type: str | None,
) -> list[str]:
    manifest = load_environment_assignments()
    definitions = manifest.get("environments", {})
    assignments = manifest.get("tool_assignments", {})
    if not isinstance(definitions, Mapping):
        raise RuntimeEnvironmentError("environments.yaml has no environments mapping")

    requested = [str(name) for name in environment_names]
    if analysis_type:
        plugin_assignments = (
            assignments.get(analysis_type, {}) if isinstance(assignments, Mapping) else {}
        )
        if not isinstance(plugin_assignments, Mapping):
            plugin_assignments = {}
        if analysis_type not in assignments:
            raise RuntimeEnvironmentError(f"Unknown ABI analysis type: {analysis_type}")
        requested.extend(str(name) for name in plugin_assignments.values())
    selected = list(dict.fromkeys(requested))
    if not selected:
        raise RuntimeEnvironmentError("Select at least one --env or --type")
    unknown = [name for name in selected if name not in definitions]
    if unknown:
        raise RuntimeEnvironmentError(f"Unknown ABI environments: {', '.join(unknown)}")
    return selected


def _render_environment_spec(environment_name: str) -> bytes:
    import yaml

    manifest = load_environment_assignments()
    definitions = manifest.get("environments", {})
    definition = definitions.get(environment_name) if isinstance(definitions, Mapping) else None
    if not isinstance(definition, Mapping):
        raise RuntimeEnvironmentError(f"Unknown ABI environment: {environment_name}")
    payload: dict[str, Any] = {"name": environment_name}
    for key in ("channel_priority", "channels", "dependencies"):
        if key in definition:
            payload[key] = definition[key]
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).encode("utf-8")


def _environment_solver_command(
    solver_name: str,
    executable: str,
    *,
    action: str,
    prefix: Path,
    spec_path: Path,
) -> list[str]:
    operation = "create" if action == "install" else "update"
    if solver_name == "micromamba":
        command = [
            executable,
            operation,
            "--yes",
            "--prefix",
            str(prefix),
            "--file",
            str(spec_path),
        ]
        if action == "update":
            command.append("--prune")
        return command
    command = [
        executable,
        "env",
        operation,
        "--prefix",
        str(prefix),
        "--file",
        str(spec_path),
    ]
    if action == "install" or solver_name == "mamba":
        command.insert(3, "--yes")
    if action == "update":
        command.append("--prune")
    return command


def _solver_process_environment(
    environ: Mapping[str, str],
    root: Path | None,
) -> dict[str, str]:
    process_env = dict(environ)
    process_env.pop("PYTHONPATH", None)
    if root is not None:
        process_env["MAMBA_ROOT_PREFIX"] = str(root)
    return process_env


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _discover_solver_root(
    environ: Mapping[str, str],
    *,
    probe: bool,
) -> MambaRootResolution | None:
    for solver_name in ("micromamba", "mamba", "conda"):
        executable = shutil.which(solver_name, path=environ.get("PATH", ""))
        if not executable:
            continue
        if not probe:
            inferred = _infer_solver_root_from_executable(solver_name, executable)
            if inferred is not None:
                return inferred
            continue
        try:
            completed = subprocess.run(
                [executable, "info", "--json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
                env=dict(environ),
            )
            payload = json.loads(completed.stdout) if completed.returncode == 0 else {}
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            continue
        root_value = payload.get("root_prefix")
        if not root_value:
            continue
        root = Path(str(root_value)).expanduser()
        if not root.is_dir():
            continue
        prefixes = tuple(
            Path(str(value)).expanduser().resolve()
            for value in payload.get("envs", [])
            if Path(str(value)).expanduser().is_dir()
        )
        return MambaRootResolution(
            root.resolve(),
            f"{solver_name}-info",
            solver=str(Path(executable).resolve()),
            known_prefixes=prefixes,
        )
    return None


def _infer_solver_root_from_executable(
    solver_name: str,
    executable: str,
) -> MambaRootResolution | None:
    resolved_executable = Path(executable).resolve()
    if resolved_executable.parent.name not in {"bin", "condabin"}:
        return None
    root = resolved_executable.parent.parent
    if not ((root / "conda-meta").is_dir() or (root / "envs").is_dir()):
        return None
    envs_dir = root / "envs"
    known_prefixes = (
        tuple(path.resolve() for path in envs_dir.iterdir() if _is_environment_prefix(path))
        if envs_dir.is_dir()
        else ()
    )
    return MambaRootResolution(
        root.resolve(),
        f"{solver_name}-executable",
        solver=str(resolved_executable),
        known_prefixes=known_prefixes,
    )


def _linux_user_mamba_root(environ: Mapping[str, str], home: Path) -> Path:
    xdg_data = environ.get("XDG_DATA_HOME")
    data_root = Path(xdg_data).expanduser() if xdg_data else home / ".local" / "share"
    return data_root / "abi" / "mamba"


def _managed_environment_count(root: Path) -> int:
    envs_dir = root / "envs"
    if not envs_dir.is_dir():
        return 0
    return sum(1 for child in envs_dir.iterdir() if _is_environment_prefix(child))


def _environment_prefix_count(root: Path) -> int:
    """Count managed and direct environment prefixes below a compatibility root."""

    if not root.is_dir():
        return 0
    count = _managed_environment_count(root)
    for child in root.iterdir():
        if child.name == "envs" or not child.is_dir():
            continue
        if _is_environment_prefix(child):
            count += 1
    return count


def _is_environment_prefix(path: Path) -> bool:
    """Return whether a directory has markers of a usable Conda environment."""

    return path.is_dir() and ((path / "conda-meta").is_dir() or (path / "bin").is_dir())


def _load_plugin_tool_metadata(analysis_type: str) -> dict[str, Mapping[str, Any]]:
    """Load registry metadata lazily to keep core configuration imports acyclic."""

    try:
        from abi.plugins import get_plugin

        registry = get_plugin(analysis_type).registry()
    except (ImportError, OSError, RuntimeError, ValueError):
        return {}
    return {
        str(metadata.get("id")): metadata
        for metadata in registry.list_tools()
        if metadata.get("id")
    }


def _match_plugin_tool(
    requested: str,
    plugin_tools: Mapping[str, Mapping[str, Any]],
) -> tuple[str, Mapping[str, Any]]:
    """Match either a registry tool ID or its declared executable."""

    if requested in plugin_tools:
        return requested, plugin_tools[requested]
    for tool_id, metadata in plugin_tools.items():
        if str(metadata.get("executable") or tool_id) == requested:
            return tool_id, metadata
    return requested, {}


def _registry_extra_path_dirs(
    metadata: Mapping[str, Any],
    *,
    env_prefix: Path | None,
    environ: Mapping[str, str],
    project_root: Path,
) -> list[Path]:
    """Resolve existing registry PATH hints without activating an environment."""

    raw_dirs = metadata.get("extra_path_dirs", [])
    if not isinstance(raw_dirs, list):
        return []
    resource_root = (
        environ.get("ABI_RESOURCE_ROOT")
        or environ.get("AUTOPLASM_RESOURCE_ROOT")
        or str(project_root / "resources" / "autoplasm")
    )
    values = {
        "project_root": str(project_root),
        "resource_root": resource_root,
        "env_prefix": str(env_prefix or ""),
    }
    paths: list[Path] = []
    seen: set[Path] = set()
    for raw in raw_dirs:
        try:
            candidate = Path(str(raw).format_map(values)).expanduser()
        except (KeyError, ValueError):
            continue
        if not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved not in seen:
            seen.add(resolved)
            paths.append(resolved)
    return paths


def _flatten_tool_assignments(raw: Any) -> dict[str, str]:
    assignments: dict[str, str] = {}
    if not isinstance(raw, Mapping):
        return assignments
    for plugin_assignments in raw.values():
        if not isinstance(plugin_assignments, Mapping):
            continue
        for tool_name, env_name in plugin_assignments.items():
            assignments.setdefault(str(tool_name), str(env_name))
    return assignments


def _normalized_architecture(machine: str) -> str:
    value = machine.lower()
    if value in {"amd64", "x86_64"}:
        return "x86_64"
    if value in {"aarch64", "arm64"}:
        return "aarch64"
    return value


__all__ = [
    "MambaRootResolution",
    "EnvironmentPrefixResolution",
    "PathResolution",
    "RuntimeEnvironmentError",
    "build_environment_report",
    "discover_mamba_root",
    "load_environment_assignments",
    "manage_environments",
    "resolve_environment_prefix",
    "resolve_executable",
    "resolve_python",
    "resolved_mamba_root",
]
