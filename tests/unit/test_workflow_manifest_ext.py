"""Extended unit tests for abi.workflow.manifest — ResourceManifest edge paths."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from abi.workflow.manifest import (
    ResourceManifest,
    _checksum_path,
    checksum_file,
    checksum_path,
)

# ── ResourceManifest.__init__ with resources list ───────────────────────


def test_resource_manifest_init_with_resources_returns_clones() -> None:
    """ResourceManifest.__init__ stores clones of resource dicts, not originals."""
    original = [
        {"id": "ref_genome", "path": "resources/genome.fa", "version": "1.0"},
    ]
    manifest = ResourceManifest("test_type", resources=original)
    # resources() returns a list copy
    res = manifest.resources
    assert len(res) == 1
    assert res[0]["id"] == "ref_genome"
    # modifying the original does not affect stored resources
    original[0]["id"] = "modified"
    assert manifest.resources[0]["id"] == "ref_genome"
    # modifying the returned list doesn't affect internal state either
    res.append({"id": "fake", "path": "nowhere"})
    assert len(manifest.resources) == 1


# ── add_resources_from_config(): non-Mapping config → early return ──────


def test_add_resources_from_config_non_mapping_returns_early() -> None:
    """add_resources_from_config() with non-Mapping resources block returns early."""
    manifest = ResourceManifest("test")
    # resources key does not exist → config.get returns empty dict
    manifest.add_resources_from_config({})
    assert manifest.resources == []

    # resources key present but not a Mapping
    manifest.add_resources_from_config({"resources": "not_a_dict"})
    assert manifest.resources == []


# ── add_resources_from_config(): with dict config ──────────────────────


def test_add_resources_from_config_with_dict_config_creates_resources(tmp_path: Path) -> None:
    """add_resources_from_config() reads path/version/source_url from dict values."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    (db_dir / "database.fa").write_text(">seq\nACGT\n")

    config: Mapping = {
        "resources": {
            "test_db": {
                "path": str(db_dir),
                "version": "2.0",
                "source_url": "https://example.com/db",
                "license": "MIT",
            },
        }
    }
    manifest = ResourceManifest("test")
    manifest.add_resources_from_config(config)
    resources = manifest.resources
    assert len(resources) == 1
    assert resources[0]["id"] == "test_db"
    assert resources[0]["path"] == str(db_dir)
    assert resources[0]["version"] == "2.0"
    assert resources[0]["source_url"] == "https://example.com/db"
    assert resources[0]["license"] == "MIT"


def test_required_resource_identities_reject_missing_version_and_source(tmp_path: Path) -> None:
    reference = tmp_path / "reference.fa"
    reference.write_text(">ref\nACGT\n", encoding="utf-8")
    manifest = ResourceManifest("test")
    manifest.add_resources_from_config(
        {"resources": {"reference_genome": str(reference)}},
    )

    assert manifest.identity_errors(["reference_genome", "mlst_db"]) == [
        "Resource 'reference_genome': missing version",
        "Resource 'reference_genome': missing source_url",
        "Resource 'mlst_db': identity is not declared",
    ]


def test_required_resource_identities_accept_complete_metadata(tmp_path: Path) -> None:
    reference = tmp_path / "reference.fa"
    reference.write_text(">ref\nACGT\n", encoding="utf-8")
    manifest = ResourceManifest("test")
    manifest.add_resources_from_config(
        {
            "provenance": {
                "resource_identities": {
                    "reference_genome": {
                        "path": str(reference),
                        "version": "GCF_000001405.40",
                        "source_url": "https://example.org/reference.fa",
                    }
                }
            }
        },
    )

    assert manifest.identity_errors(["reference_genome"]) == []


def test_required_directory_identity_requires_checksum_policy(tmp_path: Path) -> None:
    star_index = tmp_path / "star"
    star_index.mkdir()
    manifest = ResourceManifest("test")
    manifest.add_resources_from_config(
        {
            "provenance": {
                "resource_identities": {
                    "genome_index": {
                        "path": str(star_index),
                        "version": "STAR 2.7.11b + GRCh38",
                        "source_url": "https://example.org/build-recipe",
                    }
                }
            }
        }
    )

    assert manifest.identity_errors(["genome_index"]) == [
        "Resource 'genome_index': directory is not selected for SHA-256"
    ]
    assert (
        manifest.identity_errors(
            ["genome_index"],
            checksum_directory_ids=["genome_index"],
        )
        == []
    )


# ── add_resources_from_config(): with plain path config value ───────────


def test_add_resources_from_config_with_plain_path_value(tmp_path: Path) -> None:
    """add_resources_from_config() treats non-dict values as plain paths."""
    ref_file = tmp_path / "ref.fa"
    ref_file.write_text(">ref\nACGT\n")

    config: Mapping = {
        "resources": {
            "reference": str(ref_file),
        }
    }
    manifest = ResourceManifest("test")
    manifest.add_resources_from_config(config)
    resources = manifest.resources
    assert len(resources) == 1
    assert resources[0]["id"] == "reference"
    assert resources[0]["path"] == str(ref_file)


# ── validate(): missing resource path → error ──────────────────────────


def test_validate_missing_resource_path_returns_error() -> None:
    """ResourceManifest.validate() reports error for non-existent resource path."""
    manifest = ResourceManifest(
        "test", resources=[{"id": "missing_db", "path": "/nonexistent/path"}]
    )
    errors = manifest.validate()
    assert len(errors) == 1
    assert "missing_db" in errors[0]
    assert "does not exist" in errors[0]


# ── missing_resources(): returns IDs of non-existent paths ──────────────


def test_missing_resources_returns_ids_of_nonexistent_paths(tmp_path: Path) -> None:
    """missing_resources() returns IDs of resources whose paths don't exist."""
    existing = tmp_path / "exists.fa"
    existing.write_text(">seq\nACGT\n")
    manifest = ResourceManifest(
        "test",
        resources=[
            {"id": "present", "path": str(existing)},
            {"id": "missing", "path": "/no/such/path"},
            {"id": "also_missing", "path": "/another/fake/path"},
        ],
    )
    missing_ids = manifest.missing_resources()
    assert "missing" in missing_ids
    assert "also_missing" in missing_ids
    assert "present" not in missing_ids


# ── checksum_file(): path not regular file → "" ────────────────────────


def test_checksum_file_non_regular_file_returns_empty(tmp_path: Path) -> None:
    """checksum_file() returns '' when path is a directory, not a file."""
    result = checksum_file(tmp_path)  # tmp_path is a directory
    assert result == ""


def test_checksum_file_nonexistent_returns_empty() -> None:
    """checksum_file() returns '' when path does not exist."""
    result = checksum_file("/nonexistent/file_xyz.abc")
    assert result == ""


# ── _checksum_path(): dir vs file branching ────────────────────────────


def test_checksum_path_directory_returns_empty(tmp_path: Path) -> None:
    """_checksum_path() returns '' for a directory (not a file)."""
    result = _checksum_path(tmp_path)
    assert result == ""


def test_checksum_path_regular_file_returns_hash(tmp_path: Path) -> None:
    """_checksum_path() returns a hex digest for a regular file."""
    f = tmp_path / "data.txt"
    f.write_text("hello world")
    result = _checksum_path(f)
    assert len(result) == 64  # SHA-256 hex digest
    assert result == checksum_file(f)


def test_directory_resource_checksum_detects_same_size_content_change(tmp_path: Path) -> None:
    resource = tmp_path / "star_index"
    resource.mkdir()
    index = resource / "Genome"
    index.write_text("AAAA", encoding="utf-8")

    first = checksum_path(resource)
    index.write_text("TTTT", encoding="utf-8")
    second = checksum_path(resource)

    assert len(first) == 64
    assert first != second


def test_resource_manifest_validates_directory_checksum(tmp_path: Path) -> None:
    resource = tmp_path / "database"
    resource.mkdir()
    table = resource / "db.tsv"
    table.write_text("id\tvalue\nA\t1\n", encoding="utf-8")
    manifest = ResourceManifest("test")
    manifest.add_resource(
        id="database",
        path=resource,
        checksum_sha256=checksum_path(resource),
        checksum_method="sha256:content-tree-v1",
    )

    assert manifest.validate() == []
    table.write_text("id\tvalue\nA\t2\n", encoding="utf-8")
    assert "checksum mismatch" in manifest.validate()[0]


def test_resource_identity_overlay_adds_versions_sources_and_internal_databases(
    tmp_path: Path,
) -> None:
    star_index = tmp_path / "star"
    star_index.mkdir()
    (star_index / "Genome").write_text("index", encoding="utf-8")
    mlst_db = tmp_path / "mlst"
    mlst_db.mkdir()
    (mlst_db / "saureus.txt").write_text("scheme", encoding="utf-8")
    config = {
        "resources": {"genome_index": str(star_index)},
        "provenance": {
            "resource_identities": {
                "genome_index": {
                    "version": "GRCh37.75-STAR-2.7.11b",
                    "source_url": "https://example.org/grch37",
                },
                "mlst_db": {
                    "path": str(mlst_db),
                    "version": "pubmlst-2026-07-01",
                    "source_url": "https://pubmlst.org/",
                },
            }
        },
    }
    manifest = ResourceManifest("test")
    manifest.add_resources_from_config(
        config,
        checksum=True,
        checksum_directory_ids=["genome_index", "mlst_db"],
    )
    resources = {resource["id"]: resource for resource in manifest.resources}

    assert resources["genome_index"]["version"] == "GRCh37.75-STAR-2.7.11b"
    assert resources["genome_index"]["source_url"] == "https://example.org/grch37"
    assert len(resources["genome_index"]["checksum_sha256"]) == 64
    assert resources["mlst_db"]["path"] == str(mlst_db)
    assert resources["mlst_db"]["version"] == "pubmlst-2026-07-01"
    assert len(resources["mlst_db"]["checksum_sha256"]) == 64
