from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from abi.runtime_environment import (
    RuntimeEnvironmentError,
    build_environment_report,
    discover_mamba_root,
    load_environment_assignments,
    resolve_environment_prefix,
    resolve_executable,
    resolve_python,
)


def _executable(path: Path, contents: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_explicit_mamba_root_is_authoritative_and_invalid_root_fails(tmp_path: Path) -> None:
    root = tmp_path / "managed mamba"
    root.mkdir()

    resolution = discover_mamba_root(
        explicit_root=root,
        environ={"ABI_MAMBA_ROOT": str(tmp_path / "ignored")},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    assert resolution.path == root.resolve()
    assert resolution.source == "explicit"
    with pytest.raises(RuntimeEnvironmentError, match="does not exist"):
        discover_mamba_root(
            explicit_root=tmp_path / "missing",
            environ={},
            project_root=tmp_path / "project",
            home=tmp_path / "home",
        )


def test_global_micromamba_root_is_discovered_from_solver_info(tmp_path: Path) -> None:
    solver_root = tmp_path / "global-mamba"
    solver_root.mkdir()
    bin_dir = tmp_path / "global-bin"
    payload = json.dumps({"root_prefix": str(solver_root), "envs": []})
    _executable(
        bin_dir / "micromamba",
        f"#!/bin/sh\nprintf '%s' '{payload}'\n",
    )

    resolution = discover_mamba_root(
        environ={"PATH": str(bin_dir)},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    assert resolution.path == solver_root.resolve()
    assert resolution.source == "micromamba-info"
    assert resolution.solver == str((bin_dir / "micromamba").resolve())


def test_environment_prefix_prefers_managed_layout_and_tracks_known_prefixes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    direct = root / "rnaseq"
    managed = root / "envs" / "rnaseq"
    direct.mkdir(parents=True)
    managed.mkdir(parents=True)

    assert resolve_environment_prefix(root, "rnaseq").path == managed.resolve()

    external = tmp_path / "named-envs" / "wgs"
    external.mkdir(parents=True)
    resolved = resolve_environment_prefix(
        root,
        "wgs",
        known_prefixes=[external],
    )
    assert resolved.path == external.resolve()
    assert resolved.source == "solver-prefix"


def test_tool_and_python_resolution_precedence_is_explainable(tmp_path: Path) -> None:
    env_prefix = tmp_path / "env"
    env_tool = _executable(env_prefix / "bin" / "fastp")
    env_python = _executable(env_prefix / "bin" / "python")
    resource_tool = _executable(tmp_path / "resource" / "fastp")
    system_tool = _executable(tmp_path / "system" / "fastp")
    environ = {"PATH": str(system_tool.parent)}

    tool = resolve_executable(
        "fastp",
        env_prefix=env_prefix,
        extra_dirs=[resource_tool.parent],
        environ=environ,
    )
    python = resolve_python(env_prefix=env_prefix, environ=environ)
    internal_python = resolve_python(internal=True, environ=environ)

    assert tool.path == env_tool.resolve()
    assert tool.source == "environment"
    assert python.path == env_python.resolve()
    assert python.source == "environment"
    assert internal_python.path == Path(sys.executable).resolve()
    assert internal_python.source == "abi-python"


def test_environment_report_finds_assigned_and_global_tools(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    root = tmp_path / "mamba"
    env_prefix = root / "envs" / "abi-qc"
    assigned = _executable(env_prefix / "bin" / "fastp")
    global_tool = _executable(tmp_path / "global" / "custom-tool")
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "environments": {"abi-qc": {"dependencies": ["fastp"]}},
            "tool_assignments": {"demo": {"fastp": "abi-qc"}},
        },
    )

    report = build_environment_report(
        explicit_root=root,
        tool_names=["fastp", "custom-tool"],
        environ={"PATH": str(global_tool.parent)},
        project_root=project,
        home=tmp_path / "home",
    )

    assert report["platform"]["system"] == "Linux"
    assert report["mamba_root"]["path"] == str(root.resolve())
    rows = {row["tool"]: row for row in report["tools"]}
    assert rows["fastp"]["path"] == str(assigned.resolve())
    assert rows["fastp"]["source"] == "environment"
    assert rows["custom-tool"]["path"] == str(global_tool.resolve())
    assert rows["custom-tool"]["source"] == "system-path"
    assert report["healthy"] is True


def test_environment_manifest_declares_linux_only_capability_matrix() -> None:
    manifest = load_environment_assignments()
    support = manifest["platform_support"]

    assert support["active_os"] == "linux"
    assert set(support["architectures"]) == {"x86_64", "aarch64"}
    assert support["architectures"]["x86_64"]["core_status"] == "certified"
    assert support["architectures"]["aarch64"]["core_status"] == "ci_configured"
    assert set(support["plugins"]) == set(manifest["tool_assignments"])
    assert "macos" not in json.dumps(support).lower()


def test_environment_report_rejects_unsupported_plugin_architecture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    root.mkdir()
    architecture = __import__("platform").machine()
    normalized = "aarch64" if architecture in {"aarch64", "arm64"} else "x86_64"
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "platform_support": {
                "active_os": "linux",
                "plugins": {"demo": {normalized: "unsupported"}},
            },
            "environments": {},
            "tool_assignments": {"demo": {}},
        },
    )

    report = build_environment_report(
        explicit_root=root,
        analysis_type="demo",
        environ={"PATH": ""},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    assert report["plugin"]["analysis_type"] == "demo"
    assert report["plugin"]["status"] == "unsupported"
    assert f"unsupported_plugin:demo:{normalized}" in report["issues"]
    assert report["healthy"] is False
