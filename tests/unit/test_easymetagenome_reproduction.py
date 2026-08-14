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
    source_rows = freeze_core53(
        PROJECT_ROOT / "docs/zh/figures/data/easymeta_ibd_20260725/Table_1.csv",
        tmp_path / "source.tsv",
        reads_root="/data/SRP131166",
    )
    ena = tmp_path / "ena.tsv"
    ena.write_text(
        "run_accession\tfastq_ftp\tfastq_md5\tfastq_bytes\n"
        + "\n".join(
            "\t".join(
                (
                    row["sample_id"],
                    f"ftp.example/{row['sample_id']}_1.fastq.gz;"
                    f"ftp.example/{row['sample_id']}_2.fastq.gz",
                    f"{'a' * 32};{'b' * 32}",
                    "10;20",
                )
            )
            for row in source_rows
        )
        + "\n",
        encoding="utf-8",
    )

    rows = freeze_core53(
        PROJECT_ROOT / "docs/zh/figures/data/easymeta_ibd_20260725/Table_1.csv",
        output,
        reads_root="/data/SRP131166",
        ena_report=ena,
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
    assert (
        validate_core53_manifest(
            output,
            table1_path=PROJECT_ROOT / "docs/zh/figures/data/easymeta_ibd_20260725/Table_1.csv",
            require_ena_metadata=True,
        )
        == []
    )
    assert rows[0]["r1_url"].startswith("https://ftp.example/")
    assert rows[0]["r1_md5"] == "a" * 32


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


def test_formal_core53_validation_requires_ena_metadata(tmp_path):
    manifest = tmp_path / "core53.tsv"
    freeze_core53(
        PROJECT_ROOT / "docs/zh/figures/data/easymeta_ibd_20260725/Table_1.csv",
        manifest,
        reads_root="/data/SRP131166",
    )

    errors = validate_core53_manifest(manifest, require_ena_metadata=True)

    assert "Formal IBD reproduction requires ENA URL, MD5, and byte metadata" in errors


def test_formal_core53_validation_rejects_malformed_ena_metadata(tmp_path):
    manifest = tmp_path / "core53.tsv"
    rows = freeze_core53(
        PROJECT_ROOT / "docs/zh/figures/data/easymeta_ibd_20260725/Table_1.csv",
        tmp_path / "source.tsv",
        reads_root="/data/SRP131166",
    )
    fields = list(rows[0]) + ["r1_url", "r2_url", "r1_md5", "r2_md5", "r1_bytes", "r2_bytes"]
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "r1_url": "ftp://bad",
                    "r2_url": "https://ok",
                    "r1_md5": "x",
                    "r2_md5": "b" * 32,
                    "r1_bytes": "0",
                    "r2_bytes": "20",
                }
            )

    errors = validate_core53_manifest(manifest, require_ena_metadata=True)

    assert any("valid HTTPS URLs" in error for error in errors)
    assert any("valid MD5" in error for error in errors)
    assert any("positive byte counts" in error for error in errors)


def test_pluspf_identity_requires_exact_frozen_release(tmp_path):
    database = tmp_path / "database"
    database.mkdir()
    (database / "hash.k2d").write_text("frozen", encoding="utf-8")
    identity = tmp_path / ".abi_resource_identity.json"
    identity.write_text(
        json.dumps(
            {
                "database_id": "kraken2_pluspf",
                "version": "pluspf_20240605",
                "source_url": PLUSPF_20240605_SOURCE,
                "archive_sha256": "a" * 64,
                "publisher_md5_url": PLUSPF_20240605_SOURCE.replace(
                    "k2_pluspf_20240605.tar.gz", "pluspf_20240605/pluspf.md5"
                ),
                "content_sha256": (
                    "6c1895620f328cccc123f8244a786d9c552bcf9fb71e3f91401ba98feca336de"
                ),
            }
        ),
        encoding="utf-8",
    )

    assert validate_pluspf_identity(identity, resource_path=database) == []
    payload = json.loads(identity.read_text(encoding="utf-8"))
    payload["version"] = "standard_20260226"
    identity.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_pluspf_identity(identity, resource_path=database) == [
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

    substituted = score_ibd_reproduction(
        genus,
        manifest,
        reference,
        tmp_path / "substituted.json",
        permutations=9,
        method_substitutions=[{"tool": "kneaddata", "literature": "0.6.1"}],
    )
    assert substituted["status"] == "divergent"
    assert substituted["method_compatibility"] == "divergent"


def test_e1_uses_per_sample_relative_abundance(tmp_path):
    manifest = tmp_path / "samples.tsv"
    manifest.write_text(
        "sample_id\tr1\tr2\tgroup\tproject\n"
        "N1\tn1\tn2\tNC\tSRP131166\nN2\tn1\tn2\tNC\tSRP131166\n"
        "C1\tc1\tc2\tCD\tSRP131166\nC2\tc1\tc2\tCD\tSRP131166\n"
        "U1\tu1\tu2\tUC\tSRP131166\nU2\tu1\tu2\tUC\tSRP131166\n",
        encoding="utf-8",
    )
    genus = tmp_path / "genus.tsv"
    genus.write_text(
        "name\ttaxonomy_id\tN1\tN2\tC1\tC2\tU1\tU2\n"
        "A\t1\t900\t9\t100\t1\t200\t2\nB\t2\t100\t1\t900\t9\t800\t8\n",
        encoding="utf-8",
    )
    reference = tmp_path / "reference.csv"
    reference.write_text(
        "title,,,,,,,,,\n"
        "Genus,NC,CD,UC,diff_CD_NC,diff_UC_NC,diff_UC_CD,p_value_NC_vs_CD,p_value_NC_vs_UC,p_value_CD_vs_UC\n"
        "A,90,10,20,-80,-70,10,****,,\nA,90,10,20,-80,-70,10,,****,\n"
        "A,90,10,20,-80,-70,10,,,ns\nB,10,90,80,80,70,-10,****,,\n"
        "B,10,90,80,80,70,-10,,****,\nB,10,90,80,80,70,-10,,,ns\n",
        encoding="utf-8",
    )

    result = score_ibd_reproduction(
        genus, manifest, reference, tmp_path / "score.json", permutations=9
    )

    assert result["endpoints"]["E1"]["status"] == "pass"
