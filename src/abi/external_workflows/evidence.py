"""Immutable evidence archiving and checksum verification."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    path = root / "evidence_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def verify_evidence_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors: list[dict[str, str]] = []
    for row in manifest.get("files", []):
        evidence = path.parent / str(row.get("path", ""))
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
