#!/usr/bin/env python3
"""Backfill tombstones for legacy cleanup receipts from pre-deletion ABI checksums."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    provenance = args.result_dir / "provenance"
    checksums = json.loads((provenance / "checksums.json").read_text(encoding="utf-8"))
    output_dir = provenance / "tombstones"
    output_dir.mkdir(parents=True, exist_ok=True)
    explained: set[str] = set()
    for receipt_path in sorted((provenance / "intermediate_cleanup").glob("*.json")):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        deleted_roots = [Path(path) for path in receipt.get("deleted_paths", [])]
        artifacts = []
        for recorded_path, digest in checksums.items():
            path = Path(recorded_path)
            if any(path == root or path.is_relative_to(root) for root in deleted_roots):
                artifacts.append(
                    {
                        "path": recorded_path,
                        "sha256": digest,
                        "size_bytes": None,
                        "status": "deleted",
                        "hash_source": "provenance/checksums.json",
                    }
                )
                explained.add(recorded_path)
        tombstone = output_dir / receipt_path.name
        tombstone.write_text(
            json.dumps(
                {
                    "schema_version": "1.0-backfill",
                    "sample_id": receipt.get("sample_id", receipt_path.stem),
                    "cleanup_receipt": str(receipt_path),
                    "artifacts": artifacts,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    missing = {path for path in checksums if not Path(path).exists()}
    compression_missing = sorted(
        path
        for path in missing - explained
        if "/02_host_removal/" in path and path.endswith(".fastq")
    )
    by_sample: dict[str, list[str]] = {}
    for path in compression_missing:
        by_sample.setdefault(Path(path).parent.name, []).append(path)
    for sample_id, paths in by_sample.items():
        receipt = provenance / "intermediate_cleanup" / f"{sample_id}.compression.json"
        tombstone = output_dir / f"{sample_id}.compression.json"
        artifacts = [
            {
                "path": path,
                "sha256": checksums[path],
                "size_bytes": None,
                "status": "deleted",
                "hash_source": "provenance/checksums.json",
            }
            for path in paths
        ]
        receipt.write_text(
            json.dumps(
                {
                    "schema_version": "1.0-backfill",
                    "status": "success",
                    "sample_id": sample_id,
                    "operation": "compress_dehost_reads",
                    "deleted_paths": paths,
                    "tombstone_manifest": str(tombstone),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        tombstone.write_text(
            json.dumps(
                {
                    "schema_version": "1.0-backfill",
                    "sample_id": sample_id,
                    "cleanup_receipt": str(receipt),
                    "artifacts": artifacts,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        explained.update(paths)
    unexplained = sorted(missing - explained)
    print(
        json.dumps(
            {
                "checksum_entries": len(checksums),
                "missing_entries": len(missing),
                "tombstoned_entries": len(missing & explained),
                "unexplained_missing": unexplained,
            },
            indent=2,
        )
    )
    if unexplained:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
