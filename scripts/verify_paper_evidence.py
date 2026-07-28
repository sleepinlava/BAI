#!/usr/bin/env python3
"""Independently verify the three paper evidence bundles and TSV tamper detection."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from abi.evidence import verify_evidence_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "docs/paper_examples/manifests"
CASES = ("airway", "wgs", "scapp")


def verify_case(case: str, *, root: Path = ROOT) -> dict[str, Any]:
    """Verify one original bundle, then prove that a copied TSV fails after tampering."""
    manifest = root / "docs/paper_examples/manifests" / f"{case}.evidence-manifest.json"
    original = verify_evidence_manifest(manifest, artifact_root=root)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    tsv = next(
        (item for item in payload["artifacts"] if str(item["path"]).endswith(".tsv")),
        None,
    )
    if tsv is None:
        raise ValueError(f"Evidence bundle has no TSV artifact: {case}")

    with tempfile.TemporaryDirectory(prefix=f"abi-evidence-{case}-") as temp_dir:
        isolated_root = Path(temp_dir)
        isolated_manifest = isolated_root / "manifest.json"
        isolated_artifact = isolated_root / tsv["path"]
        isolated_artifact.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / tsv["path"], isolated_artifact)
        isolated_manifest.write_text(
            json.dumps(
                {
                    "schema_version": payload["schema_version"],
                    "evidence_id": payload["evidence_id"],
                    "run_id": payload["run_id"],
                    "artifacts": [tsv],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        before = verify_evidence_manifest(isolated_manifest, artifact_root=isolated_root)
        with isolated_artifact.open("a", encoding="utf-8") as handle:
            handle.write("\n# independent tamper probe\n")
        after = verify_evidence_manifest(isolated_manifest, artifact_root=isolated_root)

    return {
        "case": case,
        "original_valid": original.valid,
        "original_files_checked": original.checked,
        "tamper_probe_artifact": tsv["path"],
        "isolated_copy_valid_before_tamper": before.valid,
        "tamper_detected": not after.valid and tsv["path"] in after.mismatched,
    }


def main() -> int:
    results = [verify_case(case) for case in CASES]
    valid = all(
        result["original_valid"]
        and result["isolated_copy_valid_before_tamper"]
        and result["tamper_detected"]
        for result in results
    )
    print(json.dumps({"valid": valid, "bundles": results}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
