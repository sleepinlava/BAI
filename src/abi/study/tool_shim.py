"""Deterministic external-tool shims used only for control-flow validation."""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ShimResult:
    tool_id: str
    exit_code: int
    output_digests: dict[str, str]
    evidence_label: str = "synthetic_control_flow_evidence_not_biological_validity"


def run_tool_shim(
    *,
    tool_id: str,
    arguments: Mapping[str, Any],
    outputs: Mapping[str, Path],
    behavior: str,
    state_root: Path,
    event_log: Path,
    fail_exit_code: int = 42,
    contract_parameters: Mapping[str, Mapping[str, Any]] | None = None,
    contract_outputs: Mapping[str, Mapping[str, Any]] | None = None,
) -> ShimResult:
    """Execute a network-free deterministic shim and record cross-verifiable events."""
    if contract_parameters is not None:
        unknown = set(arguments) - set(contract_parameters)
        missing = {
            name
            for name, specification in contract_parameters.items()
            if specification.get("required", False) and name not in arguments
        }
        if unknown or missing:
            raise ValueError(
                f"Arguments do not satisfy {tool_id} contract; "
                f"unknown={sorted(unknown)}, missing={sorted(missing)}"
            )
    state_root.mkdir(parents=True, exist_ok=True)
    event_log.parent.mkdir(parents=True, exist_ok=True)
    arguments_digest = hashlib.sha256(
        json.dumps(dict(arguments), sort_keys=True, default=str).encode()
    ).hexdigest()
    _emit(
        event_log,
        "external_tool_start",
        {
            "tool_id": tool_id,
            "arguments_digest": arguments_digest,
            "behavior": behavior,
        },
    )

    state_file = state_root / f"{tool_id}.{behavior}.json"
    attempts = 0
    if state_file.exists():
        attempts = int(json.loads(state_file.read_text(encoding="utf-8"))["attempts"])
    attempts += 1
    state_file.write_text(json.dumps({"attempts": attempts}) + "\n", encoding="utf-8")

    exit_code = 0
    if behavior == "fail_once" and attempts == 1:
        exit_code = fail_exit_code
    elif behavior not in {
        "clean",
        "fail_once",
        "resume",
        "exit_zero_with_empty_gene_counts",
        "exit_zero_with_missing_required_gene_symbol_column",
        "exit_zero_with_missing_required_result_files",
    }:
        raise ValueError(f"Unknown tool-shim behavior: {behavior}")

    digests: dict[str, str] = {}
    if exit_code == 0 and behavior != "exit_zero_with_missing_required_result_files":
        for name, path in outputs.items():
            specification = (contract_outputs or {}).get(name, {})
            _write_output(
                tool_id=tool_id,
                name=name,
                path=path,
                behavior=behavior,
                specification=specification,
            )
            digests[name] = _path_digest(path)

    result = ShimResult(tool_id=tool_id, exit_code=exit_code, output_digests=digests)
    _emit(
        event_log,
        "external_tool_end",
        {
            "tool_id": tool_id,
            "exit_code": exit_code,
            "output_digests": digests,
            "evidence_label": result.evidence_label,
        },
    )
    return result


def _write_output(
    *,
    tool_id: str,
    name: str,
    path: Path,
    behavior: str,
    specification: Mapping[str, Any],
) -> None:
    if specification.get("type") == "directory":
        path.mkdir(parents=True, exist_ok=True)
        (path / "_ABI_STUDY_OUTPUT.json").write_text(
            json.dumps({"output": name, "synthetic": True}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if behavior == "exit_zero_with_empty_gene_counts":
        if "count" in name:
            path.write_text("", encoding="utf-8")
            return
    if behavior == "exit_zero_with_missing_required_gene_symbol_column":
        if tool_id == "amrfinderplus" and name in {"amr_tsv", "amrfinder_tsv"}:
            path.write_text("sample_id\tcoverage\nS1\t1.0\n", encoding="utf-8")
            return
    output_format = str(specification.get("format", path.suffix.lstrip("."))).lower()
    if output_format == "json" or path.suffix == ".json":
        path.write_text(
            json.dumps(
                {"schema": "abi-study-shim-output.v1", "output": name, "synthetic": True},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return
    if output_format in {"fasta", "fa", "fna"} or path.suffix in {".fa", ".fasta", ".fna"}:
        path.write_text(">synthetic_control_flow_sequence\nACGTACGT\n", encoding="utf-8")
        return
    if output_format in {"fastq.gz", "fq.gz"}:
        path.write_bytes(gzip.compress(b"@synthetic\nACGT\n+\nIIII\n", mtime=0))
        return
    if output_format in {"fastq", "fq"} or path.suffix in {".fastq", ".fq"}:
        path.write_text("@synthetic\nACGT\n+\nIIII\n", encoding="utf-8")
        return
    if output_format == "html":
        path.write_text(
            "<html><body>synthetic control-flow report</body></html>\n", encoding="utf-8"
        )
        return
    if output_format == "gff":
        path.write_text(
            "##gff-version 3\nsynthetic\tABI\tgene\t1\t8\t.\t+\t.\tID=g1\n", encoding="utf-8"
        )
        return
    if output_format == "gbk":
        path.write_text(
            "LOCUS       SYNTHETIC 8 bp DNA\nORIGIN\n        1 acgtacgt\n//\n",
            encoding="utf-8",
        )
        return
    if "count" in name:
        path.write_text("gene_id\tS1\nsynthetic_gene\t1\n", encoding="utf-8")
        return
    if tool_id == "amrfinderplus" and name in {"amr_tsv", "amrfinder_tsv"}:
        path.write_text(
            "Gene symbol\tSequence name\tElement type\nblaSYN\tcontig_1\tAMR\n",
            encoding="utf-8",
        )
        return
    if tool_id == "genomad" and name == "plasmid_summary":
        path.write_text("seq_name\tlength\ttopology\nplasmid_1\t8\tcircular\n", encoding="utf-8")
        return
    path.write_text(
        "record_id\tstatus\nevidence_1\tsynthetic_control_flow_only\n",
        encoding="utf-8",
    )


def _emit(path: Path, event: str, details: Mapping[str, Any]) -> None:
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": dict(details),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path_digest(path: Path) -> str:
    if path.is_file():
        return _sha256(path)
    digest = hashlib.sha256()
    for child in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(str(child.relative_to(path)).encode())
        digest.update(child.read_bytes())
    return digest.hexdigest()
