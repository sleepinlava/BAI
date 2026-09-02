"""Immutable evidence archiving and checksum verification."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from abi.filesystem import checksum_file


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Compute the file's SHA-256 via the canonical implementation (P1-4).

    ``chunk_size`` is retained for API compatibility; the canonical
    implementation streams in fixed-size chunks and produces identical
    digests regardless of chunking.
    """
    return checksum_file(path)


def sync_manifest_artifacts(manifest: dict[str, Any]) -> None:
    """Rebuild the canonical ``artifacts`` section from ``files`` rows.

    The managed runtime mutates ``manifest["files"]`` after archiving (path
    promotion, task-log collection), so the checksum section the core verifier
    reads must be derived at write time rather than maintained incrementally.
    派生而非增量维护: 每次写盘前从 files 行重建规范 artifacts 段。
    """
    manifest["artifacts"] = [
        {
            "path": str(row["path"]),
            "sha256": str(row["sha256"]),
            "size_bytes": int(row.get("size", 0) or 0),
        }
        for row in manifest.get("files", [])
        if isinstance(row, dict) and row.get("complete") and row.get("sha256")
    ]


def archive_evidence_files(
    sources: Iterable[tuple[str | Path, str]],
    bundle_dir: str | Path,
    *,
    collector_version: str,
) -> Path:
    """Copy raw evidence before parsing and write a relative checksum manifest."""
    root = Path(bundle_dir)
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for source_value, evidence_type in sources:
        source = Path(source_value)
        name = source.name
        if name in used_names:
            name = f"{evidence_type}_{name}"
        used_names.add(name)
        destination = raw_dir / name
        row: dict[str, Any] = {
            "source": str(source.resolve(strict=False)),
            "type": evidence_type,
            "collected_at": collected_at,
            "collector_version": collector_version,
            "complete": source.is_file(),
            "parse_status": "not_parsed",
        }
        if source.is_file():
            shutil.copyfile(source, destination)
            row.update(
                {
                    "path": destination.relative_to(root).as_posix(),
                    "size": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                }
            )
        else:
            row.update({"path": f"raw/{name}", "size": 0, "sha256": ""})
        rows.append(row)
    manifest = {
        "schema_version": "abi.evidence-manifest.v1",
        "collector_version": collector_version,
        "collected_at": collected_at,
        "complete": all(row["complete"] for row in rows),
        "files": rows,
    }
    # Canonical checksum section: the core verifier (abi.evidence) only reads
    # the "artifacts" key, so the bundle manifest must carry it to be
    # verifiable across implementations. Incomplete sources are excluded;
    # they stay tracked in "files" (which also carries type/source metadata).
    # 规范校验段: 核心校验器只读 "artifacts" 键, 清单必须携带它才能跨实现校验。
    sync_manifest_artifacts(manifest)
    path = root / "evidence_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def verify_evidence_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors: list[dict[str, str]] = []
    # Verify the canonical "artifacts" section when present; fall back to the
    # legacy "files" rows only when the key is ABSENT (older bundles). An
    # empty manifest — including an explicit empty "artifacts" list, which
    # the core verifier judges invalid — verifies nothing and must be
    # invalid, never vacuously valid.
    # 存在规范 "artifacts" 段时校验之（即使为空列表，与核心校验器一致判 invalid）；
    # 仅当键缺失时才回退旧版 "files" 行。空清单校验不到任何内容，
    # 必须判 invalid，绝不能空洞地判 valid。
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, list):
        entries = [
            {"path": str(item.get("path", "")), "sha256": str(item.get("sha256", ""))}
            for item in artifacts
            if isinstance(item, dict)
        ]
    else:
        entries = [
            {"path": str(row.get("path", "")), "sha256": str(row.get("sha256", ""))}
            for row in manifest.get("files", [])
            if isinstance(row, dict)
        ]
    if not entries:
        errors.append({"code": "empty_manifest", "path": str(path)})
    for row in entries:
        evidence = path.parent / row["path"]
        if not evidence.is_file():
            errors.append({"code": "missing_evidence", "path": str(evidence)})
            continue
        observed = sha256_file(evidence)
        if observed != row.get("sha256"):
            errors.append(
                {
                    "code": "checksum_mismatch",
                    "path": str(evidence),
                    "expected": str(row.get("sha256", "")),
                    "observed": observed,
                }
            )
    return {"valid": not errors and bool(manifest.get("complete")), "errors": errors}
