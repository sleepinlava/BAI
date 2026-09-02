"""Shared required-output evaluation for Bacannot process contracts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping


def evaluate_required_outputs(
    required_outputs: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    sample_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (missing, invalid) findings for one sample against contract outputs.

    ``missing`` entries report roles whose declared glob patterns yielded fewer
    files than ``min_files``; ``invalid`` entries report existing files that
    failed a declared validator.
    """
    missing: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for spec in required_outputs:
        role = str(spec.get("role", ""))
        patterns = [str(pattern) for pattern in spec.get("patterns", ())]
        min_files = int(spec.get("min_files", 1))
        validators = [str(name) for name in spec.get("validators", ())]
        matched = sorted(
            {path for pattern in patterns for path in sample_root.glob(pattern) if path.is_file()}
        )
        if len(matched) < min_files:
            missing.append(
                {
                    "role": role,
                    "patterns": patterns,
                    "min_files": min_files,
                    "found_files": len(matched),
                }
            )
            continue
        for path in matched:
            failed = [name for name in validators if not VALIDATORS[name](path)]
            if failed:
                invalid.append({"role": role, "path": str(path), "validators_failed": failed})
    return missing, invalid


def _non_empty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _fasta_parseable(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return text.lstrip().startswith(">")


def _contains_sequence(path: Path) -> bool:
    try:
        return any(
            line.strip() and not line.startswith(">")
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    except (OSError, UnicodeError):
        return False


def _gff_parseable(path: Path) -> bool:
    try:
        return any(
            len(line.split("\t")) >= 9
            for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        )
    except (OSError, UnicodeError):
        return False


def _tsv_parseable(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            return bool(reader.fieldnames) and all(
                bool(str(name).strip()) for name in reader.fieldnames or []
            )
    except (OSError, UnicodeError, csv.Error):
        return False


VALIDATORS = {
    "non_empty": _non_empty,
    "fasta_parseable": _fasta_parseable,
    "contains_sequence": _contains_sequence,
    "gff_parseable": _gff_parseable,
    "tsv_parseable": _tsv_parseable,
}
