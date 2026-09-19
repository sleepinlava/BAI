"""Cross-component persistence tests for external runtime termination facts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from abi.errors import ABIError
from abi.plugin_registry import get_plugin
from abi.runtimes.base import RuntimeOptions
from abi.runtimes.nextflow import NextflowRuntime
from abi.runtimes.snakemake import SnakemakeRuntime


def _fake_snakemake(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "fake_snakemake"
    fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)
    return fake_bin


def test_nextflow_timeout_writes_persistent_termination_evidence(tmp_path, monkeypatch):
    plugin = get_plugin("metatranscriptomics")
    config = plugin.load_config(overrides={"outdir": str(tmp_path / "results")})
    plan = plugin.build_plan(config)
    fake_bin = tmp_path / "nextflow"
    fake_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_bin.chmod(0o755)
    runtime = NextflowRuntime(
        plugin,
        options=RuntimeOptions(
            engine="nextflow",
            smoke=True,
            nextflow_bin=fake_bin,
            timeout_seconds=1,
        ),
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(kwargs.get("args", args[0] if args else []), 1)

    monkeypatch.setattr("abi.runtimes.nextflow.subprocess.run", timeout)
    with pytest.raises(ABIError, match="timed out"):
        runtime.run(plan, config)

    summary = (tmp_path / "results" / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    assert '"status": "timeout"' in summary
    assert '"scope": "nextflow_engine_process"' in summary


def test_snakemake_timeout_writes_persistent_termination_evidence(tmp_path, monkeypatch) -> None:
    plugin = get_plugin("metatranscriptomics")
    config = plugin.load_config(overrides={"outdir": str(tmp_path / "results")})
    plan = plugin.build_plan(config)
    runtime = SnakemakeRuntime(
        plugin,
        options=RuntimeOptions(
            engine="snakemake",
            smoke=True,
            snakemake_bin=_fake_snakemake(tmp_path),
            timeout_seconds=1,
        ),
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(kwargs.get("args", args[0] if args else []), 1)

    monkeypatch.setattr("abi.runtimes.snakemake.subprocess.run", timeout)
    with pytest.raises(ABIError, match="timed out"):
        runtime.run(plan, config)

    summary = (tmp_path / "results" / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    assert '"status": "timeout"' in summary
    assert '"confirmed": true' in summary
    commands = (tmp_path / "results" / "provenance" / "commands.tsv").read_text(encoding="utf-8")
    assert "timeout" in commands
