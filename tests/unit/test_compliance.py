from __future__ import annotations

import json
from pathlib import Path

from abi.compliance import audit_result


def test_audit_result_explains_deleted_checksums_with_tombstones(tmp_path: Path) -> None:
    provenance = tmp_path / "provenance"
    tombstones = provenance / "tombstones"
    tombstones.mkdir(parents=True)
    live = tmp_path / "tables" / "result.tsv"
    live.parent.mkdir()
    live.write_text("ok\n", encoding="utf-8")
    deleted = tmp_path / "reads" / "S1.fastq.gz"
    live_hash = "dc51b8c96c2d745df3bd5590d990230a482fd247123599548e0632fdbf97fc22"
    deleted_hash = "b" * 64
    (provenance / "checksums.json").write_text(
        json.dumps({str(live): live_hash, str(deleted): deleted_hash}), encoding="utf-8"
    )
    receipt = provenance / "intermediate_cleanup" / "S1.json"
    receipt.parent.mkdir()
    tombstone = tombstones / "S1.json"
    tombstone.write_text(
        json.dumps(
            {
                "sample_id": "S1",
                "cleanup_receipt": str(receipt),
                "artifacts": [{"path": str(deleted), "sha256": deleted_hash, "status": "deleted"}],
            }
        ),
        encoding="utf-8",
    )
    receipt.write_text(
        json.dumps({"status": "success", "tombstone_manifest": str(tombstone)}),
        encoding="utf-8",
    )
    (provenance / "tool_versions.tsv").write_text(
        "tool_id\texecutable\tenv_name\tversion\tstatus\nkraken2\tkraken2\te\t2.1.3\tcaptured\n",
        encoding="utf-8",
    )
    (provenance / "run_summary.json").write_text(
        json.dumps(
            {
                "status": "success",
                "git_commit": "a" * 40,
                "git_dirty": False,
                "runtime_lock_id": "sha256:" + "c" * 64,
                "runtime_lock_strict": True,
            }
        ),
        encoding="utf-8",
    )
    host_db = tmp_path / "host_db"
    host_db.mkdir()
    (host_db / "index.bt2").write_text("host", encoding="utf-8")
    (provenance / "config.resolved.yaml").write_text(
        "provenance:\n  required_resource_identity_ids: [host_db]\n", encoding="utf-8"
    )
    (provenance / "resource_manifest.json").write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "id": "host_db",
                        "path": str(host_db),
                        "version": "GRCh37",
                        "source_url": "https://example.org",
                        "checksum_sha256": (
                            "33702cb75fa9dac06992d7c2b8b0eeda728c21531f4e70969e5c34d36f4b1f46"
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = audit_result(tmp_path)

    assert result["valid"] is True
    assert result["checks"]["checksums"]["counts"] == {
        "present_verified": 1,
        "deleted_tombstoned": 1,
        "unexplained_missing": 0,
        "mismatched": 0,
    }


def test_audit_result_merges_plugin_declared_checkpoints(tmp_path: Path) -> None:
    """P2-3: plugin-owned compliance checkpoints merge into the generic audit.

    The core must no longer hardcode easymetagenome/IBD specifics: with an
    analysis_type in run_summary, the owning plugin's ``compliance_checks``
    hook supplies the extra checks; any failing check fails the audit.
    """
    from abi.plugin_registry import get_plugin

    provenance = tmp_path / "provenance"
    provenance.mkdir(parents=True)
    (provenance / "run_summary.json").write_text(
        json.dumps(
            {
                "status": "success",
                "analysis_type": "easymetagenome",
                "git_commit": "a" * 40,
                "git_dirty": False,
                "runtime_lock_id": "lock-1",
                "runtime_lock_strict": True,
            }
        ),
        encoding="utf-8",
    )
    (provenance / "tool_versions.tsv").write_text(
        "tool_id\texecutable\tenv_name\tversion\tstatus\nkraken2\tkraken2\te\t2.1.3\tcaptured\n",
        encoding="utf-8",
    )
    (provenance / "resource_manifest.json").write_text(
        json.dumps({"resources": []}), encoding="utf-8"
    )
    (provenance / "checksums.json").write_text("{}", encoding="utf-8")
    # The audit reads the resolved config from disk (post-hoc semantics).
    (provenance / "config.resolved.yaml").write_text(
        "workflow:\n  preset: ibd_core53_reproduction\n", encoding="utf-8"
    )
    config = {"workflow": {"preset": "ibd_core53_reproduction"}}

    result = audit_result(tmp_path)

    plugin = get_plugin("easymetagenome")
    assert (
        plugin.compliance_checks(tmp_path, config)["core53_manifest"]
        == result["checks"]["core53_manifest"]
    )
    # Generic checks are still present alongside the plugin's.
    assert "run_status" in result["checks"] and "checksums" in result["checks"]


def test_audit_result_skips_unknown_analysis_type(tmp_path: Path) -> None:
    provenance = tmp_path / "provenance"
    provenance.mkdir(parents=True)
    (provenance / "run_summary.json").write_text(
        json.dumps({"status": "success", "analysis_type": "not_a_real_plugin"}),
        encoding="utf-8",
    )
    (provenance / "tool_versions.tsv").write_text(
        "tool_id\texecutable\tenv_name\tversion\tstatus\n",
        encoding="utf-8",
    )
    (provenance / "resource_manifest.json").write_text(
        json.dumps({"resources": []}), encoding="utf-8"
    )
    (provenance / "checksums.json").write_text("{}", encoding="utf-8")

    result = audit_result(tmp_path)

    assert set(result["checks"]) == {
        "run_status",
        "source_identity",
        "tool_versions",
        "resource_identity",
        "checksums",
    }
