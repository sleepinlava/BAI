from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from abi.cli import app

runner = CliRunner()


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
