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
    manage_environments,
    resolve_environment_prefix,
    resolve_executable,
    resolve_python,
)


def _executable(path: Path, contents: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)
    return path


def _environment_prefix(path: Path) -> Path:
    history = path / "conda-meta" / "history"
    history.parent.mkdir(parents=True)
    history.touch()
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


def test_nonprobing_discovery_infers_standard_global_solver_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    solver_root = tmp_path / "miniconda"
    (solver_root / "conda-meta").mkdir(parents=True)
    solver = _executable(solver_root / "condabin" / "mamba")

    def _forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("nonprobing discovery must not start a subprocess")

    monkeypatch.setattr("abi.runtime_environment.subprocess.run", _forbidden)

    resolution = discover_mamba_root(
        environ={"PATH": str(solver.parent)},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
        probe_solver=False,
    )

    assert resolution.path == solver_root.resolve()
    assert resolution.source == "mamba-executable"
    assert resolution.solver == str(solver.resolve())


def test_empty_repository_root_does_not_shadow_global_solver(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".mamba").mkdir(parents=True)
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
        project_root=project,
        home=tmp_path / "home",
    )

    assert resolution.path == solver_root.resolve()
    assert resolution.source == "micromamba-info"


def test_incomplete_managed_prefix_does_not_shadow_global_solver(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".mamba" / "envs" / "interrupted" / "bin").mkdir(parents=True)
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
        project_root=project,
        home=tmp_path / "home",
    )

    assert resolution.path == solver_root.resolve()
    assert resolution.source == "micromamba-info"


def test_populated_user_root_precedes_global_solver(tmp_path: Path) -> None:
    user_root = tmp_path / "xdg-data" / "abi" / "mamba"
    _environment_prefix(user_root / "envs" / "wgs")
    solver_root = tmp_path / "global-mamba"
    solver_root.mkdir()
    bin_dir = tmp_path / "global-bin"
    payload = json.dumps({"root_prefix": str(solver_root), "envs": []})
    _executable(
        bin_dir / "micromamba",
        f"#!/bin/sh\nprintf '%s' '{payload}'\n",
    )

    resolution = discover_mamba_root(
        environ={
            "PATH": str(bin_dir),
            "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        },
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    assert resolution.path == user_root.resolve()
    assert resolution.source == "linux-user-data"


def test_environment_prefix_prefers_managed_layout_and_tracks_known_prefixes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    direct = root / "rnaseq"
    managed = root / "envs" / "rnaseq"
    _environment_prefix(direct)
    _environment_prefix(managed)

    assert resolve_environment_prefix(root, "rnaseq").path == managed.resolve()

    external = tmp_path / "named-envs" / "wgs"
    _environment_prefix(external)
    resolved = resolve_environment_prefix(
        root,
        "wgs",
        known_prefixes=[external],
    )
    assert resolved.path == external.resolve()
    assert resolved.source == "solver-prefix"


def test_incomplete_managed_prefix_does_not_shadow_valid_direct_environment(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    (root / "envs" / "wgs" / "bin").mkdir(parents=True)
    direct = root / "wgs"
    _environment_prefix(direct)

    resolved = resolve_environment_prefix(root, "wgs")

    assert resolved.path == direct.resolve()
    assert resolved.source == "direct-environment"
    assert resolved.exists is True


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


def test_explicit_executable_must_have_execute_permission(tmp_path: Path) -> None:
    tool = tmp_path / "bin" / "tool"
    tool.parent.mkdir()
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o644)

    resolution = resolve_executable(str(tool), environ={"PATH": ""})

    assert resolution.path is None
    assert resolution.source == "non-executable-explicit-executable"


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


def test_environment_report_prefers_selected_plugin_assignment_for_shared_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    selected = _executable(root / "envs" / "selected-env" / "bin" / "fastp")
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "environments": {
                "first-env": {"dependencies": ["fastp"]},
                "selected-env": {"dependencies": ["fastp"]},
            },
            "tool_assignments": {
                "first": {"fastp": "first-env"},
                "selected": {"fastp": "selected-env"},
            },
        },
    )

    report = build_environment_report(
        explicit_root=root,
        analysis_type="selected",
        tool_names=["fastp"],
        environ={"PATH": ""},
    )

    tool = report["tools"][0]
    assert tool["environment"] == "selected-env"
    assert tool["source"] == "environment"
    assert tool["path"] == str(selected.resolve())


def test_environment_report_uses_registry_executable_and_resource_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    root.mkdir()
    resource_bin = tmp_path / "resources" / "custom" / "bin"
    executable = _executable(resource_bin / "featureCounts")
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "environments": {"rnaseq": {"dependencies": []}},
            "tool_assignments": {"rnaseq_expression": {"featurecounts": "rnaseq"}},
        },
    )
    monkeypatch.setattr(
        "abi.runtime_environment._load_plugin_tool_metadata",
        lambda analysis_type: {
            "featurecounts": {
                "id": "featurecounts",
                "executable": "featureCounts",
                "extra_path_dirs": ["{resource_root}/custom/bin"],
            }
        },
    )

    report = build_environment_report(
        explicit_root=root,
        analysis_type="rnaseq_expression",
        environ={"ABI_RESOURCE_ROOT": str(tmp_path / "resources"), "PATH": ""},
    )

    tool = report["tools"][0]
    assert tool["tool_id"] == "featurecounts"
    assert tool["executable"] == "featureCounts"
    assert tool["environment"] == "rnaseq"
    assert tool["source"] == "resource-path"
    assert tool["path"] == str(executable.resolve())
    assert report["healthy"] is True


def test_environment_report_maps_explicit_executable_back_to_tool_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    executable = _executable(root / "envs" / "wgs" / "bin" / "spades.py")
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "environments": {"wgs": {"dependencies": []}},
            "tool_assignments": {"wgs_bacteria": {"spades": "wgs"}},
        },
    )
    monkeypatch.setattr(
        "abi.runtime_environment._load_plugin_tool_metadata",
        lambda analysis_type: {
            "spades": {"id": "spades", "executable": "spades.py"},
        },
    )

    report = build_environment_report(
        explicit_root=root,
        analysis_type="wgs_bacteria",
        tool_names=["spades.py"],
        environ={"PATH": ""},
    )

    tool = report["tools"][0]
    assert tool["tool"] == "spades.py"
    assert tool["tool_id"] == "spades"
    assert tool["environment"] == "wgs"
    assert tool["path"] == str(executable.resolve())


def test_environment_manifest_declares_linux_only_capability_matrix() -> None:
    manifest = load_environment_assignments()
    support = manifest["platform_support"]
    allowed_statuses = {"certified", "partial", "unsupported"}

    assert support["active_os"] == "linux"
    assert set(support["architectures"]) == {"x86_64", "aarch64"}
    assert support["architectures"]["x86_64"]["core_status"] == "certified"
    assert support["architectures"]["aarch64"]["core_status"] == "ci_configured"
    assert set(support["plugins"]) == set(manifest["tool_assignments"])
    assert set(support["environments"]) == set(manifest["environments"])
    for matrix in (support["plugins"], support["environments"]):
        for architecture_cells in matrix.values():
            assert set(architecture_cells) == {"x86_64", "aarch64"}
            for cell in architecture_cells.values():
                assert cell["status"] in allowed_statuses
                assert isinstance(cell["blockers"], list)
                assert isinstance(cell["alternatives"], list)
    assert support["tools"]["status_source"] == "assigned_environment"
    assert support["tools"]["unassigned"]["status"] == "partial"
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
                "plugins": {
                    "demo": {
                        normalized: {
                            "status": "unsupported",
                            "blockers": ["native package unavailable"],
                            "alternatives": ["use x86_64"],
                            "evidence": ["solver audit"],
                        }
                    }
                },
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
    assert report["plugin"]["blockers"] == ["native package unavailable"]
    assert report["plugin"]["alternatives"] == ["use x86_64"]
    assert f"unsupported_plugin:demo:{normalized}" in report["issues"]
    assert report["healthy"] is False


def test_environment_and_tool_reports_inherit_architecture_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    root.mkdir()
    architecture = __import__("platform").machine()
    normalized = "aarch64" if architecture in {"aarch64", "arm64"} else "x86_64"
    capability = {
        "status": "partial",
        "blockers": ["real-tool smoke pending"],
        "alternatives": ["validate before production"],
        "evidence": ["environment solve configured"],
    }
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "platform_support": {
                "active_os": "linux",
                "environments": {"demo-env": {normalized: capability}},
                "tools": {
                    "status_source": "assigned_environment",
                    "unassigned": {
                        "status": "partial",
                        "blockers": ["not assigned"],
                        "alternatives": [],
                        "evidence": [],
                    },
                },
                "plugins": {"demo": {normalized: capability}},
            },
            "environments": {"demo-env": {"dependencies": ["python=3.10"]}},
            "tool_assignments": {"demo": {"python": "demo-env"}},
        },
    )

    report = build_environment_report(
        explicit_root=root,
        analysis_type="demo",
        environ={"PATH": ""},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    environment = next(row for row in report["environments"] if row["name"] == "demo-env")
    tool = next(row for row in report["tools"] if row["tool_id"] == "python")
    assert environment["capability"] == capability
    assert tool["capability"] == capability


def test_environment_install_rejects_unsupported_architecture_before_solver_lookup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    architecture = __import__("platform").machine()
    normalized = "aarch64" if architecture in {"aarch64", "arm64"} else "x86_64"
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "platform_support": {
                "active_os": "linux",
                "environments": {
                    "blocked-env": {
                        normalized: {
                            "status": "unsupported",
                            "blockers": ["package unavailable"],
                            "alternatives": ["use a supported architecture"],
                        }
                    }
                },
            },
            "environments": {"blocked-env": {"dependencies": ["python=3.10"]}},
            "tool_assignments": {},
        },
    )

    with pytest.raises(RuntimeEnvironmentError, match="blocked-env.*unsupported"):
        manage_environments(
            action="install",
            environment_names=["blocked-env"],
            explicit_root=tmp_path / "root",
            environ={"PATH": ""},
        )


def test_plugin_install_rejects_unsupported_plugin_before_solver_lookup(
    tmp_path: Path,
) -> None:
    with pytest.raises(RuntimeEnvironmentError, match="viral_viwrap.*unsupported"):
        manage_environments(
            action="install",
            environment_names=[],
            analysis_type="viral_viwrap",
            explicit_root=tmp_path / "root",
            dry_run=True,
            environ={"PATH": ""},
        )


def test_report_rejects_plugin_whose_assigned_environment_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    root.mkdir()
    architecture = __import__("platform").machine()
    normalized = "aarch64" if architecture in {"aarch64", "arm64"} else "x86_64"
    partial = {
        "status": "partial",
        "blockers": [],
        "alternatives": [],
        "evidence": [],
    }
    unsupported = {
        "status": "unsupported",
        "blockers": ["native package unavailable"],
        "alternatives": ["use another architecture"],
        "evidence": [],
    }
    monkeypatch.setattr(
        "abi.runtime_environment.load_environment_assignments",
        lambda: {
            "platform_support": {
                "active_os": "linux",
                "architectures": {normalized: {}},
                "environments": {"blocked-env": {normalized: unsupported}},
                "plugins": {"demo": {normalized: partial}},
            },
            "environments": {"blocked-env": {"dependencies": ["python=3.10"]}},
            "tool_assignments": {"demo": {"demo-tool": "blocked-env"}},
        },
    )

    report = build_environment_report(
        explicit_root=root,
        analysis_type="demo",
        environ={"PATH": ""},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    assert f"unsupported_environment:blocked-env:{normalized}" in report["issues"]
    assert report["healthy"] is False


def test_unscoped_ambiguous_tool_assignment_requires_plugin_type(tmp_path: Path) -> None:
    root = tmp_path / "mamba"
    root.mkdir()
    tool = _executable(tmp_path / "bin" / "fastp")

    report = build_environment_report(
        explicit_root=root,
        tool_names=["fastp"],
        environ={"PATH": str(tool.parent)},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    row = report["tools"][0]
    assert row["environment"] is None
    assert {"abi-qc", "autoplasm-qc"}.issubset(row["environment_candidates"])
    assert len(row["environment_candidates"]) > 1
    assert row["capability"]["status"] == "not_declared"
    assert any(issue.startswith("ambiguous_tool_environment:fastp:") for issue in report["issues"])
    assert report["healthy"] is False


def test_unknown_linux_architecture_fails_closed_when_matrix_is_declared(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mamba"
    root.mkdir()
    monkeypatch.setattr("abi.runtime_environment.platform.machine", lambda: "ppc64le")

    report = build_environment_report(
        explicit_root=root,
        environ={"PATH": ""},
        project_root=tmp_path / "project",
        home=tmp_path / "home",
    )

    assert "unsupported_architecture:ppc64le" in report["issues"]
    assert report["healthy"] is False
    with pytest.raises(RuntimeEnvironmentError, match="Linux architecture ppc64le"):
        manage_environments(
            action="install",
            environment_names=["wgs"],
            explicit_root=tmp_path / "managed",
            dry_run=True,
            environ={"PATH": ""},
        )
