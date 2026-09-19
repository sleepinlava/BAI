from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from abi.audit import (
    AUDIT_SNAPSHOT_SCHEMA_VERSION,
    AuditSnapshotWriteError,
    audit_snapshot_status,
    build_audit_snapshot,
    load_audit_snapshot,
    write_audit_snapshot,
)


def _plugin(tmp_path: Path):
    return SimpleNamespace(
        plugin_id="test_plugin",
        root=tmp_path,
        report_title="Test report",
        table_schemas=lambda: {"summary": ["sample_id", "value"]},
    )


def test_audit_snapshot_round_trip_has_valid_status(tmp_path: Path) -> None:
    destination = write_audit_snapshot(_plugin(tmp_path), tmp_path / "provenance")

    status = audit_snapshot_status(tmp_path)

    assert destination.is_file()
    assert status["status"] == "valid"
    assert status["errors"] == []
    assert load_audit_snapshot(tmp_path)["schema_version"] == AUDIT_SNAPSHOT_SCHEMA_VERSION


def test_audit_snapshot_status_rejects_unknown_version_and_bad_schema(tmp_path: Path) -> None:
    provenance = tmp_path / "provenance"
    provenance.mkdir()
    (provenance / "audit_snapshot.json").write_text(
        json.dumps(
            {
                "schema_version": "abi.audit_snapshot.v0",
                "analysis_type": "test_plugin",
                "standard_table_schemas": {"summary": "not-a-column-list"},
                "limitations": [],
            }
        ),
        encoding="utf-8",
    )

    status = audit_snapshot_status(tmp_path)

    assert status["status"] == "invalid"
    assert any("schema_version" in error for error in status["errors"])
    assert any("summary" in error for error in status["errors"])
    assert load_audit_snapshot(tmp_path) is None


def test_audit_snapshot_status_rejects_mismatched_result_identity(tmp_path: Path) -> None:
    write_audit_snapshot(_plugin(tmp_path), tmp_path / "provenance")

    status = audit_snapshot_status(tmp_path, expected_analysis_type="other_plugin")

    assert status["status"] == "invalid"
    assert any("does not match result analysis_type" in error for error in status["errors"])


def test_audit_snapshot_status_distinguishes_missing_file(tmp_path: Path) -> None:
    status = audit_snapshot_status(tmp_path)

    assert status["status"] == "missing"
    assert status["errors"] == ["Audit snapshot is missing"]


def test_audit_snapshot_status_reports_invalid_encoding(tmp_path: Path) -> None:
    provenance = tmp_path / "provenance"
    provenance.mkdir()
    (provenance / "audit_snapshot.json").write_bytes(b"\xff\xfe")

    status = audit_snapshot_status(tmp_path)

    assert status["status"] == "invalid"
    assert "could not be read" in status["errors"][0]


def test_audit_snapshot_build_errors_are_recorded(tmp_path: Path) -> None:
    plugin = SimpleNamespace(
        plugin_id="broken_plugin",
        root=tmp_path,
        report_title="Broken report",
        table_schemas=lambda: (_ for _ in ()).throw(RuntimeError("schema unavailable")),
    )

    snapshot = build_audit_snapshot(plugin)

    assert snapshot["snapshot_errors"]
    assert "schema unavailable" in snapshot["snapshot_errors"][0]
    write_audit_snapshot(plugin, tmp_path / "provenance")
    status = audit_snapshot_status(tmp_path)
    assert status["status"] == "invalid"
    assert any("schema unavailable" in error for error in status["errors"])


def test_audit_snapshot_write_failure_is_explicit(tmp_path: Path, monkeypatch) -> None:
    def fail_write(self, *args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "write_text", fail_write)

    with pytest.raises(AuditSnapshotWriteError, match="read-only filesystem"):
        write_audit_snapshot(_plugin(tmp_path), tmp_path / "provenance", strict=True)
