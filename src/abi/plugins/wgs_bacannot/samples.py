"""ABI TSV to pinned Bacannot YAML samplesheet conversion."""

from __future__ import annotations

import csv
import gzip
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from abi.path_policy import validate_sample_id
from abi.schemas import ABISample, ABISampleContext


@dataclass(frozen=True)
class BacannotSampleSheet:
    path: Path
    sha256: str
    sample_ids: tuple[str, ...]


def load_sample_context(source: str | Path, *, check_files: bool) -> ABISampleContext:
    rows = _read_rows(source, check_files=check_files)
    samples = [
        ABISample(
            sample_id=row["sample_id"],
            platform="illumina",
            read1=row["read1"],
            read2=row["read2"],
        )
        for row in rows
    ]
    return ABISampleContext(
        samples=samples,
        multi_sample=len(samples) > 1,
        has_groups=False,
        enable_sample_analysis=len(samples) > 1,
        enable_differential_abundance=False,
    )


def convert_sample_sheet(
    source: str | Path,
    destination: str | Path,
    *,
    check_files: bool,
) -> BacannotSampleSheet:
    rows = _read_rows(source, check_files=check_files)
    payload: dict[str, list[dict[str, Any]]] = {
        "samplesheet": [
            {"id": row["sample_id"], "illumina": [row["read1"], row["read2"]]} for row in rows
        ]
    }
    rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return BacannotSampleSheet(
        path=path,
        sha256=hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
        sample_ids=tuple(row["sample_id"] for row in rows),
    )


def _read_rows(source: str | Path, *, check_files: bool) -> list[dict[str, str]]:
    path = Path(source)
    if not path.is_file():
        if check_files:
            raise ValueError(f"Sample sheet does not exist: {path}")
        return [
            {
                "sample_id": "sample",
                "read1": str(path.parent / "read1.fastq.gz"),
                "read2": str(path.parent / "read2.fastq.gz"),
            }
        ]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError("wgs_bacannot sample sheet is empty")
    observed_ids: set[str] = set()
    observed_files: set[Path] = set()
    normalized: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=2):
        raw_sample_id = str(row.get("sample_id", "")).strip()
        try:
            sample_id = validate_sample_id(raw_sample_id)
        except Exception as exc:
            raise ValueError(f"Invalid sample_id at row {index}: {raw_sample_id!r}") from exc
        if sample_id in observed_ids:
            raise ValueError(f"Duplicate sample_id at row {index}: {sample_id}")
        observed_ids.add(sample_id)
        platform = str(row.get("platform") or "illumina").strip().lower()
        if platform != "illumina":
            raise ValueError(f"Unsupported platform at row {index}: {platform}")
        reads = []
        for role in ("read1", "read2"):
            raw = str(row.get(role, "")).strip()
            if not raw:
                raise ValueError(f"Missing {role} for sample {sample_id}")
            candidate = Path(raw).expanduser().resolve(strict=False)
            if check_files and (not candidate.is_file() or not candidate.stat().st_size):
                raise ValueError(f"Missing or empty {role} for sample {sample_id}: {candidate}")
            if not str(candidate).lower().endswith((".fastq", ".fq", ".fastq.gz", ".fq.gz")):
                raise ValueError(f"Unsupported FASTQ suffix for {role}: {candidate}")
            if check_files and str(candidate).lower().endswith(".gz"):
                try:
                    with gzip.open(candidate, "rb") as compressed:
                        compressed.read(1)
                except (OSError, EOFError) as exc:
                    raise ValueError(f"Invalid gzip FASTQ for {role}: {candidate}") from exc
            reads.append(candidate)
        if reads[0] == reads[1]:
            raise ValueError(f"R1 and R2 resolve to the same physical file for {sample_id}")
        for candidate in reads:
            if candidate in observed_files:
                raise ValueError(f"Physical read file assigned more than once: {candidate}")
            observed_files.add(candidate)
        normalized.append({"sample_id": sample_id, "read1": str(reads[0]), "read2": str(reads[1])})
    return normalized
