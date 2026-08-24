"""Nextflow task-attempt evidence importer."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Callable, Iterable, Mapping

from abi.external_workflows.models import ExternalTaskAttempt


def import_nextflow_trace(
    path: str | Path,
    *,
    external_workflow_id: str,
    process_mapper: Callable[[str], str] | None = None,
) -> list[ExternalTaskAttempt]:
    """Import every trace row as one attempt without process-name folding."""
    trace_path = Path(path)
    if not trace_path.is_file():
        return []
    mapper = process_mapper or (lambda _name: "unmapped")
    with trace_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    attempts: list[ExternalTaskAttempt] = []
    for row in rows:
        normalized = {_normalize_key(key): str(value or "") for key, value in row.items()}
        process_name = _first(normalized, "process", "name")
        sample_id = _first(normalized, "tag", "sampleid", "sample")
        raw = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        attempts.append(
            ExternalTaskAttempt(
                external_workflow_id=external_workflow_id,
                task_id=_first(normalized, "taskid", "task"),
                task_hash=_first(normalized, "hash", "taskhash"),
                process_name=process_name,
                process_class=mapper(process_name) or "unmapped",
                sample_id=sample_id,
                attempt=_integer(_first(normalized, "attempt"), default=1),
                status=_first(normalized, "status").upper(),
                exit_code=_first(normalized, "exit", "exitcode"),
                executor=_first(normalized, "executor"),
                native_id=_first(normalized, "nativeid", "jobid"),
                container_ref=_first(normalized, "container"),
                container_digest=_first(normalized, "containerdigest"),
                work_dir=_first(normalized, "workdir"),
                submit_time=_first(normalized, "submit", "submittime"),
                start_time=_first(normalized, "start", "starttime"),
                complete_time=_first(normalized, "complete", "completetime"),
                duration_ms=_duration_ms(_first(normalized, "realtime", "duration")),
                requested_cpus=_float_or_none(_first(normalized, "cpus", "requestedcpus")),
                requested_memory_bytes=_size_bytes(_first(normalized, "memory", "requestedmemory")),
                peak_rss_bytes=_size_bytes(_first(normalized, "peakrss", "rss")),
                peak_vmem_bytes=_size_bytes(_first(normalized, "peakvmem", "vmem")),
                raw_trace_row_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            )
        )
    return attempts


def write_task_attempts_tsv(attempts: Iterable[ExternalTaskAttempt], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    field_names = [item.name for item in fields(ExternalTaskAttempt)]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for attempt in attempts:
            writer.writerow(attempt.to_dict())
    return destination


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _first(row: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


def _integer(value: str, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _duration_ms(value: str) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", value)
    if match:
        hours, minutes, seconds = match.groups(default="0")
        return int((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)
    units = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000}
    match = re.fullmatch(r"([0-9.]+)\s*(ms|s|m|h)", value.strip(), re.IGNORECASE)
    return int(float(match.group(1)) * units[match.group(2).lower()]) if match else None


def _size_bytes(value: str) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"([0-9.]+)\s*([kmgt]?i?b)?", value.strip(), re.IGNORECASE)
    if not match:
        return None
    amount, unit = match.groups(default="B")
    powers = {"B": 0, "KB": 1, "KIB": 1, "MB": 2, "MIB": 2, "GB": 3, "GIB": 3, "TB": 4, "TIB": 4}
    return int(float(amount) * (1024 ** powers[unit.upper()]))
