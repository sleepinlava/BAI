#!/usr/bin/env python3
"""Freeze the deployed hg19/GRCh37 KneadData index identity outside its content tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from abi.workflow.manifest import checksum_path

SOURCE = "https://huttenhower.sph.harvard.edu/kneadData_databases/Homo_sapiens_Bowtie2_v0.1.tar.gz"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    required = [
        "Homo_sapiens.1.bt2",
        "Homo_sapiens.2.bt2",
        "Homo_sapiens.3.bt2",
        "Homo_sapiens.4.bt2",
        "Homo_sapiens.rev.1.bt2",
        "Homo_sapiens.rev.2.bt2",
    ]
    missing = [name for name in required if not (args.database / name).is_file()]
    if missing:
        raise SystemExit("Missing host index files: " + ", ".join(missing))
    payload = {
        "database_id": "kneaddata_host",
        "version": "Homo_sapiens_Bowtie2_v0.1_GRCh37_hg19",
        "source_url": SOURCE,
        "archive_sha256": "28bd91e35efa686e081c0122bdfaf0d153416a1d07a33c826a059d12ac3f801f",
        "content_sha256": checksum_path(args.database),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
