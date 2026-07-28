from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from abi.cli import app
from abi.evidence import (
    build_evidence_manifest,
    derive_run_id,
    verify_evidence_manifest,
)


def test_evidence_manifest_detects_tampered_tsv(tmp_path: Path) -> None:
    table = tmp_path / "tables" / "metrics.tsv"
    table.parent.mkdir()
    table.write_text("metric\testimate\nrecall\t0.8\n", encoding="utf-8")
    manifest_path = build_evidence_manifest(
        artifact_root=tmp_path,
        paths=[table],
        output=tmp_path / "evidence_manifest.json",
        evidence_id="case-airway",
        run_id="run-123",
    )

    assert verify_evidence_manifest(manifest_path).valid is True

    table.write_text("metric\testimate\nrecall\t1.0\n", encoding="utf-8")
    result = verify_evidence_manifest(manifest_path)

    assert result.valid is False
    assert result.mismatched == ["tables/metrics.tsv"]


def test_evidence_manifest_records_manifest_identity(tmp_path: Path) -> None:
    table = tmp_path / "metrics.tsv"
    table.write_text("metric\testimate\nx\t1\n", encoding="utf-8")

    path = build_evidence_manifest(
        artifact_root=tmp_path,
        paths=[table],
        output=tmp_path / "evidence_manifest.json",
        evidence_id="case-wgs",
        run_id="run-456",
    )
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["schema_version"] == "abi.evidence-manifest.v1"
    assert record["evidence_id"] == "case-wgs"
    assert record["run_id"] == "run-456"
    assert "generated_at" not in record
    assert record["artifacts"][0]["path"] == "metrics.tsv"
    assert len(record["artifacts"][0]["sha256"]) == 64


def test_evidence_manifest_is_deterministic_for_unchanged_inputs(tmp_path: Path) -> None:
    table = tmp_path / "metrics.tsv"
    table.write_text("metric\testimate\nx\t1\n", encoding="utf-8")
    path = tmp_path / "evidence_manifest.json"
    arguments = {
        "artifact_root": tmp_path,
        "paths": [table],
        "output": path,
        "evidence_id": "case-deterministic",
        "run_id": "run-fixed",
    }

    build_evidence_manifest(**arguments)
    first = path.read_bytes()
    build_evidence_manifest(**arguments)

    assert path.read_bytes() == first


def test_verify_evidence_cli_exits_nonzero_after_tamper(tmp_path: Path) -> None:
    table = tmp_path / "metrics.tsv"
    table.write_text("metric\testimate\nx\t1\n", encoding="utf-8")
    manifest = build_evidence_manifest(
        artifact_root=tmp_path,
        paths=[table],
        output=tmp_path / "evidence_manifest.json",
        evidence_id="case-scapp",
        run_id="run-789",
    )
    runner = CliRunner()
    valid = runner.invoke(app, ["verify-evidence", str(manifest)])
    assert valid.exit_code == 0
    assert json.loads(valid.output)["valid"] is True

    table.write_text("metric\testimate\nx\t2\n", encoding="utf-8")
    invalid = runner.invoke(app, ["verify-evidence", str(manifest)])
    assert invalid.exit_code == 1
    assert json.loads(invalid.output)["mismatched"] == ["metrics.tsv"]


def test_derive_run_id_is_stable_and_changes_with_run_provenance(tmp_path: Path) -> None:
    provenance = tmp_path / "provenance"
    provenance.mkdir()
    summary = provenance / "run_summary.json"
    commands = provenance / "commands.tsv"
    summary.write_text('{"status":"success"}\n', encoding="utf-8")
    commands.write_text("step_id\tstatus\ns1\tsuccess\n", encoding="utf-8")

    first = derive_run_id(tmp_path)
    assert first == derive_run_id(tmp_path)
    assert first.startswith("legacy-sha256:")

    commands.write_text("step_id\tstatus\ns1\tfailed\n", encoding="utf-8")
    assert derive_run_id(tmp_path) != first
