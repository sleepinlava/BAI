from __future__ import annotations

import csv
import json
from pathlib import Path

from abi.plugins.easymetagenome.reproduction import (
    PLUSPF_20240605_SOURCE,
    freeze_core53,
    score_ibd_reproduction,
    validate_core53_manifest,
    validate_pluspf_identity,
)

PROJECT_ROOT = Path(__file__).parents[2]


def test_freeze_core53_is_single_project_and_deterministic(tmp_path):
    output = tmp_path / "core53.tsv"

    rows = freeze_core53(
        PROJECT_ROOT / "docs/zh/figures/data/easymeta_ibd_20260725/Table_1.csv",
        output,
        reads_root="/data/SRP131166",
    )

    assert len(rows) == 53
    assert {row["project"] for row in rows} == {"SRP131166"}
    assert {group: sum(row["group"] == group for row in rows) for group in ("NC", "CD", "UC")} == {
        "NC": 13,
        "CD": 20,
        "UC": 20,
    }
    cd_runs = [row["sample_id"] for row in rows if row["group"] == "CD"]
    assert cd_runs == sorted(cd_runs)
    assert validate_core53_manifest(output) == []


def test_core53_validation_rejects_cross_project_manifest(tmp_path):
    manifest = tmp_path / "samples.tsv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["sample_id", "r1", "r2", "group", "project"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {"sample_id": "ERR1", "r1": "a", "r2": "b", "group": "NC", "project": "OTHER"}
        )

    errors = validate_core53_manifest(manifest)

    assert any("53 samples" in error for error in errors)
    assert any("SRP131166" in error for error in errors)


def test_pluspf_identity_requires_exact_frozen_release(tmp_path):
    identity = tmp_path / ".abi_resource_identity.json"
    identity.write_text(
        json.dumps(
            {
                "database_id": "kraken2_pluspf",
                "version": "pluspf_20240605",
                "source_url": PLUSPF_20240605_SOURCE,
                "archive_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    assert validate_pluspf_identity(identity) == []
    payload = json.loads(identity.read_text(encoding="utf-8"))
    payload["version"] = "standard_20260226"
    identity.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_pluspf_identity(identity) == [
        "Kraken2 database version must be pluspf_20240605, got standard_20260226"
    ]


def test_reproduction_score_emits_all_preregistered_endpoints(tmp_path):
    manifest = tmp_path / "samples.tsv"
    manifest.write_text(
        "sample_id\tr1\tr2\tgroup\tproject\n"
        "N1\tn1\tn2\tNC\tSRP131166\n"
        "C1\tc1\tc2\tCD\tSRP131166\n"
        "U1\tu1\tu2\tUC\tSRP131166\n",
        encoding="utf-8",
    )
    genus = tmp_path / "genus.tsv"
    genus.write_text(
        "name\ttaxonomy_id\tN1\tC1\tU1\nA\t1\t90\t10\t20\nB\t2\t10\t90\t80\n",
        encoding="utf-8",
    )
    reference = tmp_path / "reference.csv"
    reference.write_text(
        "title,,,,,,,,,\n"
        "Genus,NC,CD,UC,diff_CD_NC,diff_UC_NC,diff_UC_CD,p_value_NC_vs_CD,p_value_NC_vs_UC,p_value_CD_vs_UC\n"
        "A,90,10,20,-80,-70,10,****,,\n"
        "A,90,10,20,-80,-70,10,,****,\n"
        "A,90,10,20,-80,-70,10,,,ns\n"
        "B,10,90,80,80,70,-10,****,,\n"
        "B,10,90,80,80,70,-10,,****,\n"
        "B,10,90,80,80,70,-10,,,ns\n",
        encoding="utf-8",
    )
    output = tmp_path / "score.json"

    result = score_ibd_reproduction(genus, manifest, reference, output, permutations=9)

    assert set(result["endpoints"]) == {"E1", "E2", "E3", "E4", "E5"}
    assert result["endpoints"]["E1"]["status"] == "pass"
    assert result["endpoints"]["E2"]["status"] == "pass"
    assert result["endpoints"]["E3"]["status"] == "pass"
    assert json.loads(output.read_text(encoding="utf-8"))["protocol"] == "ibd_core53"
