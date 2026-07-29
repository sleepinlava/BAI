from __future__ import annotations

import json
from pathlib import Path

import pytest

from abi.runtime_environment import RuntimeEnvironmentError, manage_environments


def _fake_micromamba(bin_dir: Path) -> Path:
    executable = bin_dir / "micromamba"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        """#!/bin/sh
set -eu
if [ "${1:-}" = "--version" ]; then
  printf '%s\n' '2.1.0'
  exit 0
fi
operation="${1:-}"
if [ "$operation" = "env" ]; then
  operation="${2:-}"
fi
if [ -n "${ABI_TEST_COMMAND_LOG:-}" ]; then
  printf '%s\n' "$*" >> "$ABI_TEST_COMMAND_LOG"
fi
prefix=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--prefix" ]; then
    shift
    prefix="$1"
  fi
  shift
done
if [ "$operation" = "update" ] && [ ! -d "$prefix/conda-meta" ]; then
  printf '%s\n' 'No prefix found. Environment must first be created.' >&2
  exit 7
fi
mkdir -p "$prefix/conda-meta"
: > "$prefix/conda-meta/history"
printf '%s\n' "$MAMBA_ROOT_PREFIX" > "$ABI_TEST_ROOT_LOG"
printf '%s\n' "${PYTHONPATH-unset}" > "$ABI_TEST_PYTHONPATH_LOG"
printf '%s\n' "${LD_LIBRARY_PATH-unset}" > "$ABI_TEST_LD_LIBRARY_PATH_LOG"
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _version_only_solver(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"--version\" ]; then printf '%s\\n' 'conda 25.5.0'; exit 0; fi\n"
        "exit 98\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_install_creates_user_environment_with_sanitized_solver_process(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    solver = _fake_micromamba(bin_dir)
    root_log = tmp_path / "root.log"
    pythonpath_log = tmp_path / "pythonpath.log"
    ld_library_log = tmp_path / "ld-library.log"
    xdg_data = tmp_path / "xdg-data"
    environ = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "XDG_DATA_HOME": str(xdg_data),
        "PYTHONPATH": "/host/python",
        "LD_LIBRARY_PATH": "/host/lib",
        "ABI_TEST_ROOT_LOG": str(root_log),
        "ABI_TEST_PYTHONPATH_LOG": str(pythonpath_log),
        "ABI_TEST_LD_LIBRARY_PATH_LOG": str(ld_library_log),
    }

    report = manage_environments(
        action="install",
        environment_names=["wgs"],
        environ=environ,
    )

    root = xdg_data / "abi" / "mamba"
    result = report["environments"][0]
    assert report["solver"] == {
        "name": "micromamba",
        "executable": str(solver.resolve()),
        "version": "2.1.0",
        "source": "auto",
    }
    assert report["mamba_root"] == {
        "path": str(root.resolve()),
        "source": "linux-user-data-write",
    }
    assert result["name"] == "wgs"
    assert result["status"] == "created"
    assert result["prefix"] == str((root / "envs" / "wgs").resolve())
    assert result["spec_path"] == str((root / "specs" / "wgs.yml").resolve())
    assert len(result["spec_sha256"]) == 64
    assert (root / "envs" / "wgs" / "conda-meta").is_dir()
    assert json.loads(json.dumps(report)) == report
    assert root_log.read_text(encoding="utf-8").strip() == str(root.resolve())
    assert pythonpath_log.read_text(encoding="utf-8").strip() == "unset"
    assert ld_library_log.read_text(encoding="utf-8").strip() == "/host/lib"


def test_install_is_idempotent_when_environment_already_exists(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _fake_micromamba(bin_dir)
    command_log = tmp_path / "commands.log"
    environ = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        "ABI_TEST_ROOT_LOG": str(tmp_path / "root.log"),
        "ABI_TEST_PYTHONPATH_LOG": str(tmp_path / "pythonpath.log"),
        "ABI_TEST_LD_LIBRARY_PATH_LOG": str(tmp_path / "ld-library.log"),
        "ABI_TEST_COMMAND_LOG": str(command_log),
    }

    first = manage_environments(
        action="install",
        environment_names=["wgs"],
        environ=environ,
    )
    second = manage_environments(
        action="install",
        environment_names=["wgs"],
        environ=environ,
    )

    assert first["environments"][0]["status"] == "created"
    assert second["environments"][0]["status"] == "unchanged"
    assert second["environments"][0]["executed"] is False
    assert len(command_log.read_text(encoding="utf-8").splitlines()) == 1


def test_update_creates_missing_environment_then_updates_it(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    solver = _fake_micromamba(bin_dir)
    command_log = tmp_path / "commands.log"
    environ = {
        "PATH": "/usr/bin:/bin",
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        "ABI_TEST_ROOT_LOG": str(tmp_path / "root.log"),
        "ABI_TEST_PYTHONPATH_LOG": str(tmp_path / "pythonpath.log"),
        "ABI_TEST_LD_LIBRARY_PATH_LOG": str(tmp_path / "ld-library.log"),
        "ABI_TEST_COMMAND_LOG": str(command_log),
    }

    first = manage_environments(
        action="update",
        environment_names=["wgs"],
        solver=solver,
        environ=environ,
    )
    second = manage_environments(
        action="update",
        environment_names=["wgs"],
        solver=solver,
        environ=environ,
    )

    assert first["solver"]["source"] == "explicit"
    assert first["environments"][0]["status"] == "created"
    assert second["environments"][0]["status"] == "updated"
    commands = command_log.read_text(encoding="utf-8").splitlines()
    assert len(commands) == 2
    assert commands[0].startswith("create --yes --prefix ")
    assert commands[1].startswith("env update --yes --prefix ")
    assert "--prune" not in commands[0]
    assert commands[1].endswith("--prune")


def test_conda_update_uses_documented_noninteractive_command_surface(tmp_path: Path) -> None:
    solver = _version_only_solver(tmp_path / "bin" / "conda")
    history = tmp_path / "managed-root" / "envs" / "wgs" / "conda-meta" / "history"
    history.parent.mkdir(parents=True)
    history.touch()

    report = manage_environments(
        action="update",
        environment_names=["wgs"],
        solver=solver,
        explicit_root=tmp_path / "managed-root",
        dry_run=True,
        environ={"PATH": "/usr/bin:/bin"},
    )

    command = report["environments"][0]["command"]
    assert command[:3] == [str(solver.resolve()), "env", "update"]
    assert "--yes" not in command
    assert "--prune" in command


def test_solver_failure_does_not_publish_unapplied_environment_spec(tmp_path: Path) -> None:
    solver = tmp_path / "bin" / "micromamba"
    solver.parent.mkdir()
    solver.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"--version\" ]; then printf '%s\\n' '2.1.0'; exit 0; fi\n"
        "printf '%s\\n' 'solve failed' >&2\n"
        "exit 7\n",
        encoding="utf-8",
    )
    solver.chmod(0o755)
    root = tmp_path / "managed-root"

    with pytest.raises(RuntimeEnvironmentError, match="solve failed"):
        manage_environments(
            action="install",
            environment_names=["wgs"],
            solver=solver,
            explicit_root=root,
            environ={"PATH": "/usr/bin:/bin"},
        )

    assert (root / "specs" / "wgs.yml").exists() is False


def test_partial_conda_metadata_after_failure_is_retried(tmp_path: Path) -> None:
    solver = tmp_path / "bin" / "micromamba"
    command_log = tmp_path / "commands.log"
    solver.parent.mkdir()
    solver.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"--version\" ]; then printf '%s\\n' '2.1.0'; exit 0; fi\n"
        f"printf '%s\\n' \"$*\" >> {command_log}\n"
        "prefix=''\n"
        'while [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "--prefix" ]; then shift; prefix="$1"; fi\n'
        "  shift\n"
        "done\n"
        'mkdir -p "$prefix/conda-meta"\n'
        "printf '%s\\n' 'linking failed' >&2\n"
        "exit 7\n",
        encoding="utf-8",
    )
    solver.chmod(0o755)
    root = tmp_path / "managed-root"

    for _ in range(2):
        with pytest.raises(RuntimeEnvironmentError, match="linking failed"):
            manage_environments(
                action="install",
                environment_names=["wgs"],
                solver=solver,
                explicit_root=root,
                environ={"PATH": "/usr/bin:/bin"},
            )

    assert len(command_log.read_text(encoding="utf-8").splitlines()) == 2
    assert (root / "envs" / "wgs" / "conda-meta").is_dir()
    assert (root / "envs" / "wgs" / "conda-meta" / "history").exists() is False


def test_managed_root_rejects_existing_non_directory_even_in_dry_run(tmp_path: Path) -> None:
    solver = _version_only_solver(tmp_path / "bin" / "conda")
    root = tmp_path / "managed-root"
    root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(RuntimeEnvironmentError, match="not a directory"):
        manage_environments(
            action="install",
            environment_names=["wgs"],
            solver=solver,
            explicit_root=root,
            dry_run=True,
            environ={"PATH": "/usr/bin:/bin"},
        )


def test_install_reports_unverified_spec_for_preexisting_environment(tmp_path: Path) -> None:
    solver = _version_only_solver(tmp_path / "bin" / "conda")
    root = tmp_path / "managed-root"
    history = root / "envs" / "wgs" / "conda-meta" / "history"
    history.parent.mkdir(parents=True)
    history.touch()

    report = manage_environments(
        action="install",
        environment_names=["wgs"],
        solver=solver,
        explicit_root=root,
        environ={"PATH": "/usr/bin:/bin"},
    )

    result = report["environments"][0]
    assert result["status"] == "unchanged"
    assert result["executed"] is False
    assert result["spec_state"] == "missing"
    assert (root / "specs" / "wgs.yml").exists() is False


def test_selection_error_precedes_solver_discovery() -> None:
    with pytest.raises(RuntimeEnvironmentError, match="Select at least one"):
        manage_environments(
            action="install",
            environment_names=[],
            environ={"PATH": ""},
        )


def test_environment_management_rejects_non_linux_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("abi.runtime_environment.platform.system", lambda: "Darwin")

    with pytest.raises(RuntimeEnvironmentError, match="support Linux only"):
        manage_environments(
            action="install",
            environment_names=["wgs"],
            environ={"PATH": ""},
        )
