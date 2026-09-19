"""Cross-component safeguards for managed external workflows."""

from __future__ import annotations

import gzip
import json
import subprocess
from pathlib import Path

import pytest

from abi.errors import ABIError
from abi.plugin_registry import get_plugin
from abi.runtimes.base import RuntimeOptions
from abi.runtimes.nextflow import NextflowRuntime


def _managed_fixture(tmp_path: Path):
    read1 = tmp_path / "S1_R1.fastq.gz"
    read2 = tmp_path / "S1_R2.fastq.gz"
    read1.write_bytes(gzip.compress(b"@r1\nACGT\n+\nFFFF\n"))
    read2.write_bytes(gzip.compress(b"@r2\nTGCA\n+\nFFFF\n"))
    sheet = tmp_path / "samples.tsv"
    sheet.write_text(
        f"sample_id\tplatform\tread1\tread2\nS1\tillumina\t{read1}\t{read2}\n",
        encoding="utf-8",
    )
    database = tmp_path / "db"
    database.mkdir()
    fake = tmp_path / "nextflow"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    plugin = get_plugin("wgs_bacannot")
    config = plugin.load_config(
        overrides={
            "outdir": str(tmp_path / "result"),
            "input": {"sample_sheet": str(sheet)},
            "resources": {"bacannot_db": str(database)},
        }
    )
    plan = plugin.build_plan(config)
    runtime = NextflowRuntime(
        plugin,
        options=RuntimeOptions(engine="nextflow", nextflow_bin=fake, smoke=True),
    )
    return config, plan, runtime


def test_managed_real_run_fails_closed_when_process_images_are_not_declared(tmp_path: Path):
    config, plan, runtime = _managed_fixture(tmp_path)
    runtime.options.smoke = False

    with pytest.raises(ABIError, match="finite local container image set"):
        runtime.run(plan, config)


def test_managed_nextflow_timeout_persists_termination_evidence(tmp_path: Path, monkeypatch):
    config, plan, runtime = _managed_fixture(tmp_path)
    config.setdefault("execution", {})["nextflow_timeout_seconds"] = 1

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(kwargs.get("args", args[0] if args else []), 1)

    monkeypatch.setattr("abi.external_workflows.runtime.subprocess.run", timeout)
    with pytest.raises(ABIError, match="TimeoutExpired"):
        runtime.run(plan, config)

    summary = json.loads(
        (Path(config["outdir"]) / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "timeout"
    assert summary["termination"] == {
        "request": "timeout",
        "requested": True,
        "confirmed": True,
        "scope": "managed_nextflow_engine_process",
        "downstream_status": "unknown",
        "timeout_seconds": 1,
    }
