from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence" / "linux_x86_64_capability_20260729.json"


def test_linux_x86_capability_checkpoint_matches_manifest_blockers() -> None:
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    manifest = yaml.safe_load((ROOT / "environments.yaml").read_text(encoding="utf-8"))
    declared = set(manifest["environments"])
    missing = set(payload["missing_environments"])

    assert payload["platform"] == {"system": "Linux", "architecture": "x86_64"}
    assert payload["declared_environment_count"] == len(declared) == 21
    assert payload["completed_environment_count"] + len(missing) == len(declared)
    assert missing == {"autoplasm-checkm2", "autoplasm-rgi", "autoplasm-scapp"}
    assert missing <= declared
    assert all(row["status"] == "passed" for row in payload["representative_smokes"])
    assert any("No Linux aarch64" in item for item in payload["limitations"])

    matrix = manifest["platform_support"]["environments"]
    for environment_name in missing:
        cell = matrix[environment_name]["x86_64"]
        assert cell["status"] == "partial"
        assert any("no completed canonical prefix" in blocker for blocker in cell["blockers"])

    plasmid = manifest["platform_support"]["plugins"]["metagenomic_plasmid"]["x86_64"]
    assert plasmid["status"] == "partial"
    assert set(missing) <= set(" ".join(plasmid["blockers"]).replace(",", "").split())
