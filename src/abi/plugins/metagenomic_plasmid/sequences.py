"""FASTA sequence utilities for the metagenomic plasmid plugin.

Moved out of the retired ``_engine.pipeline`` execution module (WP2): these
are biological sequence helpers, not execution logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

__all__ = ["read_fasta_records", "fasta_record", "terminal_overlap_length"]


def read_fasta_records(path: Path) -> List[Dict[str, str]]:
    """Parse a FASTA file into ``{"id": ..., "description": ..., "sequence": ...}`` records."""
    records: List[Dict[str, str]] = []
    header = ""
    sequence_lines: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n\r")
            if line.startswith(">"):
                if header:
                    records.append(fasta_record(header, sequence_lines))
                header = line[1:].strip()
                sequence_lines = []
            elif header:
                sequence_lines.append(line.strip())
    if header:
        records.append(fasta_record(header, sequence_lines))
    return records


def fasta_record(header: str, sequence_lines: Iterable[str]) -> Dict[str, str]:
    """Build one FASTA record dict from a header line and sequence lines.

    Keys (``id`` / ``header`` / ``sequence``) match the retired engine's
    record shape exactly — consumers depend on ``header`` being the full
    header line.
    """
    sequence = "".join(sequence_lines)
    return {
        "id": header.split()[0] if header else "",
        "header": header,
        "sequence": sequence,
    }


def terminal_overlap_length(sequence: str, *, minimum: int = 20, maximum: int = 1000) -> int:
    """Return the longest exact prefix/suffix overlap within conservative bounds."""
    upper = min(maximum, len(sequence) // 2)
    for size in range(upper, minimum - 1, -1):
        if sequence[:size] == sequence[-size:]:
            return size
    return 0
