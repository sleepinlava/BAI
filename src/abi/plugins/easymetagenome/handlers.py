"""Internal handlers for the ABI-native EasyMetagenome workflows."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Sequence

from abi.filesystem import checksum_file
from abi.internal import FunctionInternalHandler, InternalHandlerContext, InternalHandlerResult

from .adapters import ManifestValidator, merge_bracken, parse_fastp_json, taxonomy_diversity
from .report_manifest import write_report_manifest
from .reproduction import score_ibd_reproduction

_GZIP_CHUNK_SIZE = 8 * 1024 * 1024
_GZIP_COMPRESSION_LEVEL = 6


def _sha256(path: Path) -> str:
    """Compute the file's SHA-256 via the canonical implementation (P1-4)."""
    return checksum_file(path)


def _write_tombstone_manifest(
    *, sample_id: str, receipt: Path, artifacts: list[dict[str, Any]]
) -> Path:
    tombstone = receipt.parent.parent / "tombstones" / receipt.name
    tombstone.parent.mkdir(parents=True, exist_ok=True)
    tombstone.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sample_id": sample_id,
                "cleanup_receipt": str(receipt),
                "artifacts": artifacts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return tombstone


def _tombstone_file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
        "status": "deleted",
    }


def _paths(value: Any) -> list[Path]:
    if isinstance(value, (list, tuple)):
        return [Path(str(item)) for item in value if item]
    return [Path(str(value))] if value else []


def _write_rows(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["sample_id"]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    return destination


def validate_manifest_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del context
    manifest = config["input"]["sample_sheet"]
    reproduction = config.get("reproduction", {})
    streaming_inputs = bool(
        isinstance(reproduction, Mapping) and reproduction.get("streaming_inputs")
    )
    records = ManifestValidator.validate(manifest, check_files=not streaming_inputs)
    _write_rows(step.outputs["normalized_manifest"], [record.as_dict() for record in records])
    report = {
        "status": "pass",
        "sample_count": len(records),
        "manifest": str(Path(manifest).resolve()),
    }
    report_path = Path(step.outputs["validation_report"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return InternalHandlerResult(message=f"Validated {len(records)} samples")


def _verify_transfer(path: Path, *, url: str, expected_md5: str, expected_bytes: int) -> None:
    size = path.stat().st_size
    if size != expected_bytes:
        raise ValueError(
            f"Downloaded byte count mismatch for {url}: expected {expected_bytes}, got {size}"
        )
    digest = hashlib.md5()  # noqa: S324 - ENA publishes MD5 as a transfer-integrity checksum.
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    observed_md5 = digest.hexdigest()
    if observed_md5 != expected_md5.lower():
        raise ValueError(
            f"Downloaded MD5 mismatch for {url}: expected {expected_md5}, got {observed_md5}"
        )


def _download_verified_urllib(
    url: str, destination: Path, expected_md5: str, expected_bytes: int
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    part.unlink(missing_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as response, part.open("wb") as handle:
            while chunk := response.read(8 * 1024 * 1024):
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        _verify_transfer(part, url=url, expected_md5=expected_md5, expected_bytes=expected_bytes)
        os.replace(part, destination)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def _download_verified_aria2c(
    url: str,
    destination: Path,
    expected_md5: str,
    expected_bytes: int,
    *,
    connections: int,
) -> None:
    """Resume an ENA transfer with aria2 and publish only after full verification."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    if destination.is_file():
        _verify_transfer(
            destination, url=url, expected_md5=expected_md5, expected_bytes=expected_bytes
        )
        return
    command = [
        "aria2c",
        f"--dir={destination.parent}",
        f"--out={part.name}",
        "--continue=true",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--file-allocation=none",
        f"--max-connection-per-server={connections}",
        f"--split={connections}",
        "--min-split-size=16M",
        "--connect-timeout=30",
        "--timeout=60",
        "--max-tries=0",
        "--retry-wait=5",
        "--lowest-speed-limit=1K",
        "--async-dns=false",
        "--console-log-level=warn",
        "--summary-interval=0",
        url,
    ]
    subprocess.run(command, check=True)  # noqa: S603 - fixed executable and validated arguments.
    _verify_transfer(part, url=url, expected_md5=expected_md5, expected_bytes=expected_bytes)
    os.replace(part, destination)
    part.with_name(part.name + ".aria2").unlink(missing_ok=True)


def _download_verified_script(
    url: str,
    destination: Path,
    expected_md5: str,
    expected_bytes: int,
    *,
    script: Path,
    connections: int,
) -> None:
    """Run the durable cloud transfer script, then atomically publish verified data."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    if destination.is_file():
        _verify_transfer(
            destination, url=url, expected_md5=expected_md5, expected_bytes=expected_bytes
        )
        return
    subprocess.run(
        [str(script), url, str(part), str(connections)],
        check=True,
        stdout=subprocess.DEVNULL,
    )  # noqa: S603 - configured script path is checked by preflight.
    _verify_transfer(part, url=url, expected_md5=expected_md5, expected_bytes=expected_bytes)
    os.replace(part, destination)
    part.with_name(part.name + ".aria2").unlink(missing_ok=True)


def download_ena_reads_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    """Atomically stage one paired ENA run and verify its frozen transfer metadata."""
    reproduction = config.get("reproduction", {})
    backend = str(reproduction.get("download_backend", "urllib"))
    connections = int(reproduction.get("connections_per_file", 4))
    if backend not in {"urllib", "aria2c", "script"}:
        raise ValueError(f"Unsupported ENA download backend: {backend}")
    if not 1 <= connections <= 16:
        raise ValueError("reproduction.connections_per_file must be between 1 and 16")
    outputs = {key: Path(step.outputs[key]) for key in ("read1", "read2")}
    outdir = context.outdir.resolve()
    for path in outputs.values():
        if not path.resolve().is_relative_to(outdir):
            raise ValueError(f"Refusing to stage ENA input outside result directory: {path}")
    for mate in ("r1", "r2"):
        destination = outputs["read1" if mate == "r1" else "read2"]
        arguments = (
            str(step.inputs[f"{mate}_url"]),
            destination,
            str(step.inputs[f"{mate}_md5"]),
            int(step.inputs[f"{mate}_bytes"]),
        )
        if backend == "script":
            script = Path(str(reproduction.get("download_script", "")))
            if not script.is_file() or not os.access(script, os.X_OK):
                raise ValueError(f"ENA download script is not executable: {script}")
            _download_verified_script(
                *arguments,
                script=script,
                connections=connections,
            )
        elif backend == "aria2c":
            _download_verified_aria2c(*arguments, connections=connections)
        else:
            _download_verified_urllib(*arguments)
    receipt = Path(step.outputs["download_receipt"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(
            {
                "status": "success",
                "sample_id": str(step.sample_id),
                "read1": str(outputs["read1"]),
                "read2": str(outputs["read2"]),
                "r1_md5": str(step.inputs["r1_md5"]),
                "r2_md5": str(step.inputs["r2_md5"]),
                "r1_bytes": int(step.inputs["r1_bytes"]),
                "r2_bytes": int(step.inputs["r2_bytes"]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return InternalHandlerResult(
        message=f"Downloaded and verified ENA reads for {step.sample_id}",
        artifacts={"download_receipt": receipt},
    )


def fastp_summary_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del config, context
    rows = parse_fastp_json(_paths(step.inputs.get("fastp_json")))
    _write_rows(step.outputs["summary_table"], rows)
    return InternalHandlerResult(message=f"Summarized fastp for {len(rows)} samples")


def _fastq_records(path: Path) -> int:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle) // 4


def kneaddata_summary_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del config
    paths = _paths(step.inputs.get("dehost_reads"))
    rows: list[dict[str, Any]] = []
    reused_standard_table = any(not path.is_file() for path in paths)
    if reused_standard_table:
        sample_ids = {path.name.split("_1_kneaddata", 1)[0] for path in paths}
        table_path = context.tables_dir / "host_removal_summary.tsv"
        with table_path.open("r", encoding="utf-8", newline="") as handle:
            seen = set()
            for record in csv.DictReader(handle, delimiter="\t"):
                sample_id = str(record.get("sample_id", ""))
                if sample_id not in sample_ids or sample_id in seen:
                    continue
                rows.append(
                    {
                        "sample_id": sample_id,
                        "dehost_read_pairs": str(record.get("dehost_read_pairs", "")),
                    }
                )
                seen.add(sample_id)
    else:
        rows = [
            {
                "sample_id": path.name.split("_1_kneaddata", 1)[0],
                "dehost_read_pairs": _fastq_records(path),
            }
            for path in paths
        ]
    _write_rows(step.outputs["summary_table"], rows)
    return InternalHandlerResult(
        message=f"Summarized KneadData for {len(rows)} samples",
        tables={} if reused_standard_table else {"host_removal_summary": rows},
    )


def kneaddata_cleanup_summary_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del config, context
    rows = []
    for path in _paths(step.inputs.get("cleanup_receipts")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "sample_id": payload["sample_id"],
                "dehost_read_pairs": payload["dehost_read_pairs"],
            }
        )
    _write_rows(step.outputs["summary_table"], rows)
    return InternalHandlerResult(
        message=f"Summarized KneadData cleanup receipts for {len(rows)} samples",
        tables={"host_removal_summary": rows},
    )


def bracken_merge_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del config, context
    for level, input_key, output_key in (
        ("P", "phylum_tables", "phylum_table"),
        ("G", "genus_tables", "genus_table"),
        ("S", "species_tables", "species_table"),
    ):
        files = _paths(step.inputs.get(input_key))
        if not files:
            raise ValueError(f"No Bracken {level} tables were provided")
        merge_bracken(files, step.outputs[output_key])
    return InternalHandlerResult(message="Merged Bracken P/G/S tables")


def _filter_prevalence(source: Path, destination: Path, threshold: float) -> None:
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    fields = list(rows[0]) if rows else ["name", "taxonomy_id"]
    sample_fields = fields[2:]
    retained = [
        row
        for row in rows
        if sample_fields
        and sum(float(row.get(field) or 0) > 0 for field in sample_fields) / len(sample_fields)
        >= threshold
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(retained)


def taxonomy_filter_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del config, context
    threshold = float(step.params.get("prevalence", 0.2))
    for source_key, output_key in (
        ("phylum_table", "filtered_phylum"),
        ("genus_table", "filtered_genus"),
        ("species_table", "filtered_species"),
    ):
        _filter_prevalence(Path(step.inputs[source_key]), Path(step.outputs[output_key]), threshold)
    return InternalHandlerResult(message="Filtered taxonomy tables by prevalence")


def taxonomy_diversity_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del config, context
    alpha, beta = taxonomy_diversity(
        step.inputs["species_table"],
        step.outputs["alpha_table"],
        step.outputs["beta_table"],
    )
    return InternalHandlerResult(
        message="Computed Shannon and Bray-Curtis diversity",
        artifacts={"alpha": alpha, "beta": beta},
    )


def report_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    manifest = ManifestValidator.validate(config["input"]["sample_sheet"], check_files=False)
    report_path = Path(step.outputs["report_markdown"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    inputs = {
        key: Path(str(value))
        for key, value in step.inputs.items()
        if isinstance(value, (str, Path))
    }
    lines = [
        "# EasyMetagenome ABI Report",
        "",
        f"Input samples: {len(manifest)}",
        "",
        "## Result tables",
        "",
    ]
    for name, path in sorted(inputs.items()):
        lines.append(f"- {name}: `{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_path = write_report_manifest(
        step.outputs["report_manifest"],
        workflow="p0_taxonomy",
        sample_count=len(manifest),
        artifacts=inputs,
        report=report_path,
        tables_dir=context.tables_dir,
        table_names=("qc_summary", "host_removal_summary", "taxonomy_abundance"),
    )
    return InternalHandlerResult(
        message="EasyMetagenome report generated",
        artifacts={"report": report_path, "manifest": manifest_path},
    )


def concat_reads_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    """Concatenate paired gzip streams into one valid HUMAnN input stream."""
    del config, context
    destination = Path(step.outputs["merged_reads"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output_handle:
        for key in ("dehost_read1", "dehost_read2"):
            with Path(step.inputs[key]).open("rb") as input_handle:
                shutil.copyfileobj(input_handle, output_handle)
    return InternalHandlerResult(
        message="Concatenated paired host-filtered reads",
        artifacts={"merged_reads": destination},
    )


def score_ibd_reproduction_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del context
    result = score_ibd_reproduction(
        step.inputs["genus_table"],
        config["input"]["sample_sheet"],
        step.inputs["reference_table"],
        step.outputs["endpoint_scores"],
        permutations=int(step.params.get("permutations", 999)),
        seed=int(step.params.get("seed", 20240605)),
        method_substitutions=list(config.get("reproduction", {}).get("method_substitutions", [])),
    )
    return InternalHandlerResult(
        message=f"IBD core53 endpoint status: {result['status']}",
        artifacts={"endpoint_scores": Path(step.outputs["endpoint_scores"])},
    )


def ibd_reproduction_report_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    samples = ManifestValidator.validate(config["input"]["sample_sheet"], check_files=False)
    scores = json.loads(Path(step.inputs["endpoint_scores"]).read_text(encoding="utf-8"))
    artifacts = {key: Path(str(value)) for key, value in step.inputs.items()}
    report = Path(step.outputs["report_markdown"])
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# IBD core-53 reproduction", "", f"Overall: **{scores['status']}**", ""]
    for endpoint, payload in scores["endpoints"].items():
        lines.append(f"- {endpoint}: **{payload['status']}**")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = write_report_manifest(
        step.outputs["report_manifest"],
        workflow="ibd_core53_reproduction",
        sample_count=len(samples),
        artifacts=artifacts,
        report=report,
        tables_dir=context.tables_dir,
        table_names=("qc_summary", "host_removal_summary", "taxonomy_abundance"),
        extra={"endpoint_status": scores["status"], "endpoints": scores["endpoints"]},
    )
    return InternalHandlerResult(
        message=f"Published IBD reproduction report: {scores['status']}",
        artifacts={"report": report, "manifest": manifest},
    )


def compress_reads_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    """Compress KneadData's plain FASTQ outputs and remove them after success."""
    del context
    requested_threads = max(1, int(step.params.get("threads", config.get("threads", 1))))
    execution = config.get("execution", {})
    concurrent_steps = max(1, int(execution.get("workers", 1))) if execution.get("parallel") else 1
    compression_workers = max(1, requested_threads // concurrent_steps)
    pairs = [
        (Path(step.inputs[key]), Path(step.outputs[key]))
        for key in ("dehost_read1", "dehost_read2")
    ]
    temporary: list[tuple[Path, Path]] = []
    try:
        for source, destination in pairs:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged = destination.with_name(f".{destination.name}.tmp")
            temporary.append((staged, destination))
            _parallel_gzip(source, staged, workers=compression_workers)
        for staged, destination in temporary:
            staged.replace(destination)
    except Exception:
        for staged, _ in temporary:
            staged.unlink(missing_ok=True)
        raise

    tombstones = [_tombstone_file(source) for source, _ in pairs]
    source_bytes = sum(item["size_bytes"] for item in tombstones)
    for source, _ in pairs:
        source.unlink()
    deleted_bytes, deleted_paths, extra_tombstones = _cleanup_kneaddata_intermediates(
        pairs[0][0].parent,
        keep={destination.resolve() for _, destination in pairs},
    )
    tombstones.extend(extra_tombstones)
    deleted_paths = [str(source) for source, _ in pairs] + deleted_paths
    receipt = Path(step.outputs["cleanup_receipt"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    tombstone_manifest = _write_tombstone_manifest(
        sample_id=str(step.sample_id), receipt=receipt, artifacts=tombstones
    )
    receipt.write_text(
        json.dumps(
            {
                "status": "success",
                "sample_id": str(step.sample_id),
                "deleted_bytes": source_bytes + deleted_bytes,
                "deleted_paths": deleted_paths,
                "tombstone_manifest": str(tombstone_manifest),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return InternalHandlerResult(
        message=(
            f"Compressed paired host-filtered reads; "
            f"removed_intermediates={len(deleted_paths)}; freed_bytes={deleted_bytes}; "
            f"workers={compression_workers}"
        ),
        artifacts={
            **{key: Path(step.outputs[key]) for key in ("dehost_read1", "dehost_read2")},
            "cleanup_receipt": receipt,
            "tombstone_manifest": tombstone_manifest,
        },
    )


def _cleanup_kneaddata_intermediates(
    output_dir: Path,
    *,
    keep: set[Path],
) -> tuple[int, list[str], list[dict[str, Any]]]:
    """Remove non-final files left by KneadData after paired reads are compressed."""
    deleted_bytes = 0
    deleted_paths: list[str] = []
    tombstones: list[dict[str, Any]] = []
    if not output_dir.is_dir():
        return deleted_bytes, deleted_paths, tombstones
    keep_resolved = {path.resolve() for path in keep}
    for path in output_dir.iterdir():
        resolved = path.resolve()
        if resolved in keep_resolved or path.name.endswith(".log"):
            continue
        if path.is_symlink() or path.is_file():
            if path.is_file():
                tombstones.append(_tombstone_file(path))
            deleted_bytes += path.lstat().st_size
            path.unlink()
            deleted_paths.append(str(path))
        elif path.is_dir():
            deleted_bytes += sum(
                child.stat().st_size for child in path.rglob("*") if child.is_file()
            )
            shutil.rmtree(path)
            deleted_paths.append(str(path))
    return deleted_bytes, deleted_paths, tombstones


def _compress_gzip_member(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=_GZIP_COMPRESSION_LEVEL, mtime=0)


def _parallel_gzip(source: Path, destination: Path, *, workers: int) -> None:
    """Write ordered gzip members while compressing bounded chunks concurrently."""
    pending: deque[Future[bytes]] = deque()
    max_pending = workers + 1
    with (
        source.open("rb") as input_handle,
        destination.open("wb") as output_handle,
        ThreadPoolExecutor(max_workers=workers) as executor,
    ):
        while chunk := input_handle.read(_GZIP_CHUNK_SIZE):
            pending.append(executor.submit(_compress_gzip_member, chunk))
            if len(pending) >= max_pending:
                output_handle.write(pending.popleft().result())
        while pending:
            output_handle.write(pending.popleft().result())


def cleanup_functional_intermediates_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    """Remove large per-sample FASTQ intermediates after HUMAnN4 succeeds."""
    del config
    sample_id = str(step.sample_id)
    dehost_read_pairs = _fastq_records(Path(step.inputs["dehost_read1"]))
    intermediates = [
        Path(step.inputs[key])
        for key in ("clean_read1", "clean_read2", "dehost_read1", "dehost_read2", "merged_reads")
    ]
    outdir = context.outdir.resolve()
    deleted_bytes = 0
    deleted_paths: list[str] = []
    tombstones: list[dict[str, Any]] = []
    for path in intermediates:
        resolved = path.resolve()
        if not resolved.is_relative_to(outdir):
            raise ValueError(f"Refusing to clean intermediate outside result directory: {path}")
        if path.is_file():
            tombstones.append(_tombstone_file(path))
            deleted_bytes += path.stat().st_size
            path.unlink()
            deleted_paths.append(str(path))

    humann_output_dir = Path(step.inputs["humann_output_dir"])
    if not humann_output_dir.resolve().is_relative_to(outdir):
        raise ValueError(
            f"Refusing to clean HUMAnN intermediates outside result directory: {humann_output_dir}"
        )
    humann_temp_dir = humann_output_dir / f"{sample_id}_humann_temp"
    if humann_temp_dir.is_dir():
        tombstones.extend(
            _tombstone_file(item) for item in humann_temp_dir.rglob("*") if item.is_file()
        )
        deleted_bytes += sum(
            item.stat().st_size for item in humann_temp_dir.rglob("*") if item.is_file()
        )
        shutil.rmtree(humann_temp_dir)
        deleted_paths.append(str(humann_temp_dir))

    receipt = Path(step.outputs["cleanup_receipt"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    tombstone_manifest = _write_tombstone_manifest(
        sample_id=sample_id, receipt=receipt, artifacts=tombstones
    )
    receipt.write_text(
        json.dumps(
            {
                "status": "success",
                "sample_id": sample_id,
                "dehost_read_pairs": dehost_read_pairs,
                "deleted_bytes": deleted_bytes,
                "deleted_paths": deleted_paths,
                "tombstone_manifest": str(tombstone_manifest),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return InternalHandlerResult(
        message=f"Cleaned {len(deleted_paths)} FASTQ intermediates for {sample_id}",
        artifacts={"cleanup_receipt": receipt, "tombstone_manifest": tombstone_manifest},
    )


def cleanup_taxonomy_intermediates_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    """Remove large per-sample read/classification intermediates after Bracken succeeds."""
    del config
    sample_id = str(step.sample_id)
    dehost_read_pairs = _fastq_records(Path(step.inputs["dehost_read1"]))
    intermediates = [
        Path(step.inputs[key])
        for key in (
            "raw_read1",
            "raw_read2",
            "clean_read1",
            "clean_read2",
            "dehost_read1",
            "dehost_read2",
            "classifications",
        )
        if step.inputs.get(key)
    ]
    outdir = context.outdir.resolve()
    deleted_bytes = 0
    deleted_paths: list[str] = []
    tombstones: list[dict[str, Any]] = []
    for path in intermediates:
        resolved = path.resolve()
        if not resolved.is_relative_to(outdir):
            raise ValueError(f"Refusing to clean intermediate outside result directory: {path}")
        if path.is_file():
            tombstones.append(_tombstone_file(path))
            deleted_bytes += path.stat().st_size
            path.unlink()
            deleted_paths.append(str(path))

    receipt = Path(step.outputs["cleanup_receipt"])
    receipt.parent.mkdir(parents=True, exist_ok=True)
    tombstone_manifest = _write_tombstone_manifest(
        sample_id=sample_id, receipt=receipt, artifacts=tombstones
    )
    receipt.write_text(
        json.dumps(
            {
                "status": "success",
                "sample_id": sample_id,
                "dehost_read_pairs": dehost_read_pairs,
                "deleted_bytes": deleted_bytes,
                "deleted_paths": deleted_paths,
                "tombstone_manifest": str(tombstone_manifest),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return InternalHandlerResult(
        message=f"Cleaned {len(deleted_paths)} taxonomy intermediates for {sample_id}",
        artifacts={"cleanup_receipt": receipt, "tombstone_manifest": tombstone_manifest},
    )


def _read_humann_table(path: Path, feature_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header: list[str] | None = None
        for values in reader:
            if not values:
                continue
            if values[0].startswith("#"):
                if len(values) > 1:
                    header = values
                continue
            if header is None:
                continue
            feature_id = values[0]
            for sample_id, value in zip(header[1:], values[1:]):
                rows.append(
                    {
                        "sample_id": sample_id.rsplit("-RPKs", 1)[0],
                        "feature_type": feature_type,
                        "feature_id": feature_id,
                        "value": value,
                        "stratified": "|" in feature_id,
                        "source_file": str(path),
                    }
                )
    return rows


def functional_report_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    del config, context
    sources = {
        "gene_family": Path(step.inputs["gene_families"]),
        "ko": Path(step.inputs["ko_table"]),
        "pathway": Path(step.inputs["pathway_table"]),
    }
    rows = [
        row
        for feature_type, path in sources.items()
        for row in _read_humann_table(path, feature_type)
    ]
    report_path = Path(step.outputs["report_markdown"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# EasyMetagenome HUMAnN4 Functional Report\n\n"
        f"Normalized feature observations: {len(rows)}\n\n"
        + "\n".join(f"- {name}: `{path}`" for name, path in sources.items())
        + "\n",
        encoding="utf-8",
    )
    return InternalHandlerResult(
        message=f"Collected {len(rows)} HUMAnN feature observations",
        artifacts={"report": report_path},
    )


def publish_functional_report_handler(
    step: Any,
    config: Mapping[str, Any],
    context: InternalHandlerContext,
) -> InternalHandlerResult:
    samples = ManifestValidator.validate(config["input"]["sample_sheet"], check_files=False)
    sources = {
        "gene_family": Path(step.inputs["gene_families"]),
        "ko": Path(step.inputs["ko_table"]),
        "pathway": Path(step.inputs["pathway_table"]),
    }
    feature_observations = sum(
        len(_read_humann_table(path, feature_type)) for feature_type, path in sources.items()
    )
    manifest_path = write_report_manifest(
        step.outputs["report_manifest"],
        workflow="p1_humann4",
        sample_count=len(samples),
        artifacts=sources,
        report=step.inputs["report_markdown"],
        tables_dir=context.tables_dir,
        table_names=("functional_abundance",),
        extra={"feature_observations": feature_observations},
    )
    return InternalHandlerResult(
        message="Published EasyMetagenome functional report manifest",
        artifacts={"manifest": manifest_path},
    )


def handlers() -> dict[str, FunctionInternalHandler]:
    return {
        "easymetagenome.validate_manifest": FunctionInternalHandler(
            "easymetagenome.validate_manifest", validate_manifest_handler, "driver"
        ),
        "easymetagenome.fastp_summary": FunctionInternalHandler(
            "easymetagenome.fastp_summary", fastp_summary_handler
        ),
        "easymetagenome.kneaddata_summary": FunctionInternalHandler(
            "easymetagenome.kneaddata_summary", kneaddata_summary_handler
        ),
        "easymetagenome.kneaddata_cleanup_summary": FunctionInternalHandler(
            "easymetagenome.kneaddata_cleanup_summary", kneaddata_cleanup_summary_handler
        ),
        "easymetagenome.compress_reads": FunctionInternalHandler(
            "easymetagenome.compress_reads", compress_reads_handler
        ),
        "easymetagenome.bracken_merge": FunctionInternalHandler(
            "easymetagenome.bracken_merge", bracken_merge_handler
        ),
        "easymetagenome.taxonomy_filter": FunctionInternalHandler(
            "easymetagenome.taxonomy_filter", taxonomy_filter_handler
        ),
        "easymetagenome.taxonomy_diversity": FunctionInternalHandler(
            "easymetagenome.taxonomy_diversity", taxonomy_diversity_handler
        ),
        "easymetagenome.report": FunctionInternalHandler("easymetagenome.report", report_handler),
        "easymetagenome.score_ibd_reproduction": FunctionInternalHandler(
            "easymetagenome.score_ibd_reproduction", score_ibd_reproduction_handler
        ),
        "easymetagenome.ibd_reproduction_report": FunctionInternalHandler(
            "easymetagenome.ibd_reproduction_report", ibd_reproduction_report_handler
        ),
        "easymetagenome.concat_reads": FunctionInternalHandler(
            "easymetagenome.concat_reads", concat_reads_handler
        ),
        "easymetagenome.cleanup_functional_intermediates": FunctionInternalHandler(
            "easymetagenome.cleanup_functional_intermediates",
            cleanup_functional_intermediates_handler,
        ),
        "easymetagenome.cleanup_taxonomy_intermediates": FunctionInternalHandler(
            "easymetagenome.cleanup_taxonomy_intermediates",
            cleanup_taxonomy_intermediates_handler,
        ),
        "easymetagenome.download_ena_reads": FunctionInternalHandler(
            "easymetagenome.download_ena_reads", download_ena_reads_handler
        ),
        "easymetagenome.functional_report": FunctionInternalHandler(
            "easymetagenome.functional_report", functional_report_handler
        ),
        "easymetagenome.publish_functional_report": FunctionInternalHandler(
            "easymetagenome.publish_functional_report", publish_functional_report_handler
        ),
    }
