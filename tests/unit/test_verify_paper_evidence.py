"""Tests for the independent paper evidence verifier."""

from __future__ import annotations

import json
from pathlib import Path

from abi.evidence import build_evidence_manifest
from scripts.verify_paper_evidence import verify_case


def test_verify_case_detects_tampered_tsv_without_modifying_original(tmp_path: Path) -> None:
    table = tmp_path / "tables" / "standard.tsv"
    table.parent.mkdir(parents=True)
    table.write_text("sample\tvalue\nS1\t1\n", encoding="utf-8")
    manifest_dir = tmp_path / "docs/paper_examples/manifests"
    build_evidence_manifest(
        artifact_root=tmp_path,
        paths=[table],
        output=manifest_dir / "airway.evidence-manifest.json",
        evidence_id="test-airway",
        run_id="run-1",
    )
    before = table.read_bytes()

    result = verify_case("airway", root=tmp_path)

    assert result["original_valid"] is True
    assert result["all_tsv_copies_valid_before_tamper"] is True
    assert result["all_tsv_tampering_detected"] is True
    assert result["tsv_files_checked"] == 1
    assert table.read_bytes() == before
    payload = json.loads(
        (manifest_dir / "airway.evidence-manifest.json").read_text(encoding="utf-8")
    )
    assert payload["artifacts"][0]["path"] == "tables/standard.tsv"
