"""Portable evidence manifests for claim-level audit bundles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from abi.workflow.manifest import checksum_file

__all__ = [
    "EvidenceVerification",
    "build_evidence_manifest",
    "derive_run_id",
    "verify_evidence_manifest",
]


@dataclass(frozen=True)
class EvidenceVerification:
    """Result of independently verifying an evidence manifest."""

    valid: bool
    checked: int
    missing: list[str]
    mismatched: list[str]


def derive_run_id(result_dir: str | Path) -> str:
    """Return an existing run ID or derive a stable identity for a legacy run."""
    root = Path(result_dir)
    summary_path = root / "provenance" / "run_summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        run_id = str(summary.get("run_id", "")).strip()
        if run_id:
            return run_id
    identity_files = [
        root / "provenance" / "run_summary.json",
        root / "provenance" / "commands.tsv",
        root / "provenance" / "checksums.json",
        root / "provenance" / "config.resolved.yaml",
    ]
    digest_payload = []
    for path in identity_files:
        if path.is_file():
            digest_payload.append(f"{path.name}\0{checksum_file(path)}\n")
    if not digest_payload:
        raise FileNotFoundError(f"No run provenance found under {root}")
    digest = hashlib.sha256("".join(digest_payload).encode("utf-8")).hexdigest()
    return f"legacy-sha256:{digest}"


def build_evidence_manifest(
    *,
    artifact_root: str | Path,
    paths: Iterable[str | Path],
    output: str | Path,
    evidence_id: str,
    run_id: str,
) -> Path:
    """Write a portable manifest binding evidence files to SHA-256 digests."""
    root = Path(artifact_root).resolve()
    output_path = Path(output)
    artifacts: list[dict[str, str | int]] = []
    for candidate in paths:
        path = Path(candidate).resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Evidence artifact is outside artifact root: {path}") from exc
        if not path.is_file():
            raise FileNotFoundError(f"Evidence artifact is not a file: {path}")
        artifacts.append(
            {
                "path": relative.as_posix(),
                "sha256": checksum_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    payload = {
        "schema_version": "abi.evidence-manifest.v1",
        "evidence_id": evidence_id,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"])),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path


def verify_evidence_manifest(
    manifest: str | Path,
    *,
    artifact_root: str | Path | None = None,
) -> EvidenceVerification:
    """Verify every file in an evidence manifest without trusting its producer."""
    manifest_path = Path(manifest).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "abi.evidence-manifest.v1":
        raise ValueError("Unsupported evidence manifest schema")
    root = Path(artifact_root).resolve() if artifact_root else manifest_path.parent
    missing: list[str] = []
    mismatched: list[str] = []
    checked = 0
    for artifact in payload.get("artifacts", []):
        relative = Path(str(artifact["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe evidence artifact path: {relative}")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Evidence artifact escapes artifact root: {relative}") from exc
        if not path.is_file():
            missing.append(relative.as_posix())
            continue
        checked += 1
        if checksum_file(path) != str(artifact.get("sha256", "")):
            mismatched.append(relative.as_posix())
    return EvidenceVerification(
        valid=not missing and not mismatched,
        checked=checked,
        missing=missing,
        mismatched=mismatched,
    )
