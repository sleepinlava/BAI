from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from abi.cli import app

runner = CliRunner()


def _fake_solver(path: Path) -> Path:
    path.parent.mkdir(parents=True)
    path.write_text(
        "#!/bin/sh\n"
        "if [ \"${1:-}\" = \"--version\" ]; then printf '%s\\n' '2.1.0'; exit 0; fi\n"
        "exit 99\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_env_discover_reports_explicit_linux_root_as_json(tmp_path: Path) -> None:
    root = tmp_path / "managed mamba"
    root.mkdir()

    result = runner.invoke(
        app,
        ["env", "discover", "--mamba-root", str(root), "--output-json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["platform"]["system"] == "Linux"
    assert payload["mamba_root"]["path"] == str(root.resolve())
    assert payload["mamba_root"]["source"] == "explicit"


def test_env_doctor_resolves_requested_global_tool(tmp_path: Path) -> None:
    root = tmp_path / "mamba"
    root.mkdir()
    tool = tmp_path / "bin" / "demo-tool"
    tool.parent.mkdir()
    tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    tool.chmod(0o755)

    result = runner.invoke(
        app,
        [
            "env",
            "doctor",
            "--mamba-root",
            str(root),
            "--tool",
            "demo-tool",
            "--output-json",
        ],
        env={"PATH": str(tool.parent)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["healthy"] is True
    assert payload["tools"][0]["path"] == str(tool.resolve())
    assert payload["tools"][0]["source"] == "system-path"


def test_env_discover_rejects_missing_explicit_root(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "env",
            "discover",
            "--mamba-root",
            str(tmp_path / "missing"),
            "--output-json",
        ],
    )

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_env_install_dry_run_selects_plugin_environments_without_writing(
    tmp_path: Path,
) -> None:
    solver = _fake_solver(tmp_path / "bin" / "micromamba")
    root = tmp_path / "managed-root"

    result = runner.invoke(
        app,
        [
            "env",
            "install",
            "--type",
            "rnaseq_expression",
            "--solver",
            str(solver),
            "--mamba-root",
            str(root),
            "--dry-run",
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["action"] == "install"
    assert payload["dry_run"] is True
    assert payload["solver"]["source"] == "explicit"
    assert [row["name"] for row in payload["environments"]] == ["rnaseq"]
    assert payload["environments"][0]["status"] == "planned_create"
    assert root.exists() is False


def test_env_update_dry_run_plans_create_when_environment_is_missing(tmp_path: Path) -> None:
    solver = _fake_solver(tmp_path / "bin" / "micromamba")

    result = runner.invoke(
        app,
        [
            "env",
            "update",
            "--env",
            "wgs",
            "--solver",
            str(solver),
            "--mamba-root",
            str(tmp_path / "managed-root"),
            "--dry-run",
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["action"] == "update"
    assert payload["environments"][0]["name"] == "wgs"
    assert payload["environments"][0]["status"] == "planned_create"
    assert "--prune" not in payload["environments"][0]["command"]
