"""Resource manifest generation and validation for ABI workflows.

# Purpose / 目的
Generates a ``resource_manifest.json`` that records every database,
reference genome, index file, and curated dataset used in a pipeline run.
Without a resource manifest, a workflow can only be called "runnable" —
not "reproducible".

# Why this exists / 为何需要此模块
Bioinformatics pipelines depend on external resources: reference genomes,
taxonomic databases, functional annotations, resistance gene catalogs, etc.
These resources have versions, checksums, download URLs, and licenses.
The resource manifest captures all of this so that:
- A reviewer can verify which database version was used.
- A colleague can reproduce the exact analysis.
- An agent can detect missing or outdated resources.

# Format / 格式
The manifest is a JSON file at ``provenance/resource_manifest.json``:
```json
{
  "analysis_type": "rnaseq_expression",
  "generated_at": "2026-06-18T12:00:00Z",
  "resources": [
    {
      "id": "reference_genome",
      "path": "resources/hg38/genome.fa",
      "version": "GRCh38.p14",
      "source_url": "https://...",
      "checksum_sha256": "...",
      "license": "unknown",
      "validated_at": "2026-06-18"
    }
  ]
}
```
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

__all__ = [
    "ResourceManifest",
    "generate_resource_manifest",
    "write_resource_manifest",
    "checksum_file",
    "checksum_path",
]


class ResourceManifest:
    """Holds and validates a collection of pipeline resources.

    # Usage / 用法
        manifest = ResourceManifest(analysis_type="rnaseq_expression")
        manifest.add_resource(
            id="reference_genome",
            path="resources/hg38/genome.fa",
            version="GRCh38.p14",
            source_url="https://...",
        )
        manifest.write(result_dir / "provenance")
    """

    def __init__(
        self,
        analysis_type: str = "unknown",
        *,
        resources: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> None:
        self.analysis_type = analysis_type
        self._resources: List[Dict[str, Any]] = []
        if resources:
            for r in resources:
                self._resources.append(dict(r))

    def add_resource(
        self,
        *,
        id: str,
        path: str | Path,
        version: str = "",
        source_url: str = "",
        license: str = "",
        checksum_sha256: str = "",
        checksum_method: str = "",
        validated_at: str = "",
    ) -> None:
        """Add a resource entry to the manifest."""
        entry: Dict[str, Any] = {
            "id": id,
            "path": str(path),
            "version": version,
            "source_url": source_url,
            "checksum_sha256": checksum_sha256,
            "checksum_method": checksum_method
            or ("sha256:file-content" if checksum_sha256 and Path(path).is_file() else ""),
            "license": license,
            "validated_at": validated_at or _now_iso(),
        }
        self._resources.append(entry)

    def add_resources_from_config(
        self,
        config: Mapping[str, Any],
        *,
        checksum: bool = False,
        checksum_directory_ids: Sequence[str] = (),
    ) -> None:
        """Scan a plugin config's ``resources`` block and add entries.

        Each key in the ``resources`` dict becomes a resource ``id``.
        If the value is a dict, ``path``, ``version``, ``source_url``,
        and ``license`` are read from its keys.  Otherwise the value is
        treated as a filesystem path.
        """
        resources = config.get("resources", {})
        if not isinstance(resources, Mapping):
            resources = {}
        provenance = config.get("provenance", {})
        identity_block = (
            provenance.get("resource_identities", {}) if isinstance(provenance, Mapping) else {}
        )
        identities = identity_block if isinstance(identity_block, Mapping) else {}
        directory_ids = {str(item) for item in checksum_directory_ids}
        for key in sorted(set(resources) | set(identities)):
            if key in ("root",):
                continue
            value = resources.get(key)
            identity_value = identities.get(key, {})
            identity = dict(identity_value) if isinstance(identity_value, Mapping) else {}
            if isinstance(value, Mapping) or identity:
                resource = dict(value) if isinstance(value, Mapping) else {}
                resource.update(identity)
                res_path = Path(
                    str(
                        resource.get(
                            "path",
                            resource.get(
                                "database",
                                resource.get("directory", value if value is not None else ""),
                            ),
                        )
                    )
                )
                declared_checksum = str(
                    resource.get("checksum_sha256", resource.get("checksum", ""))
                ).strip()
                computed_checksum = ""
                checksum_method = ""
                if declared_checksum:
                    computed_checksum = declared_checksum
                    checksum_method = str(resource.get("checksum_method", "sha256:declared"))
                elif checksum and (res_path.is_file() or str(key) in directory_ids):
                    computed_checksum = checksum_path(res_path)
                    checksum_method = (
                        "sha256:file-content" if res_path.is_file() else "sha256:content-tree-v1"
                    )
                self.add_resource(
                    id=str(key),
                    path=res_path,
                    version=str(resource.get("version", "")),
                    source_url=str(resource.get("source_url", resource.get("url", ""))),
                    license=str(resource.get("license", "")),
                    checksum_sha256=computed_checksum,
                    checksum_method=checksum_method,
                )
            else:
                res_path = Path(str(value))
                should_checksum = checksum and (res_path.is_file() or str(key) in directory_ids)
                self.add_resource(
                    id=str(key),
                    path=res_path,
                    checksum_sha256=checksum_path(res_path) if should_checksum else "",
                    checksum_method=(
                        "sha256:file-content"
                        if should_checksum and res_path.is_file()
                        else (
                            "sha256:content-tree-v1"
                            if should_checksum and res_path.is_dir()
                            else ""
                        )
                    ),
                )

    @property
    def resources(self) -> List[Dict[str, Any]]:
        """All resource entries as a list of dicts."""
        return list(self._resources)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-ready dict."""
        return {
            "analysis_type": self.analysis_type,
            "generated_at": _now_iso(),
            "resources": self._resources,
        }

    def write(self, output_dir: str | Path) -> Path:
        """Write ``resource_manifest.json`` to *output_dir*."""
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        out = directory / "resource_manifest.json"
        out.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return out

    def validate(self) -> List[str]:
        """Check all resources: return a list of error messages (empty = all ok)."""
        errors: List[str] = []
        for r in self._resources:
            path = Path(r["path"])
            if not path.exists():
                errors.append(f"Resource '{r['id']}': path does not exist: {path}")
                continue
            if r.get("checksum_sha256"):
                actual = checksum_path(path)
                if actual != r["checksum_sha256"]:
                    errors.append(
                        f"Resource '{r['id']}': checksum mismatch. "
                        f"Expected {r['checksum_sha256'][:12]}..., "
                        f"got {actual[:12]}..."
                    )
        return errors

    def missing_resources(self) -> List[str]:
        """Return IDs of resources whose paths do not exist."""
        return [r["id"] for r in self._resources if not Path(r["path"]).exists()]

    def identity_errors(
        self,
        required_ids: Sequence[str],
        *,
        checksum_directory_ids: Sequence[str] = (),
    ) -> List[str]:
        """Return missing identity fields for resources required by a formal run."""
        by_id = {str(resource.get("id", "")): resource for resource in self._resources}
        directory_ids = {str(resource_id) for resource_id in checksum_directory_ids}
        errors: List[str] = []
        for resource_id in required_ids:
            resource = by_id.get(str(resource_id))
            if resource is None:
                errors.append(f"Resource '{resource_id}': identity is not declared")
                continue
            for field in ("path", "version", "source_url"):
                if not str(resource.get(field, "")).strip():
                    errors.append(f"Resource '{resource_id}': missing {field}")
            path = Path(str(resource.get("path", "")))
            if path.is_dir() and not resource.get("checksum_sha256"):
                if str(resource_id) not in directory_ids:
                    errors.append(
                        f"Resource '{resource_id}': directory is not selected for SHA-256"
                    )
        return errors


# ── Convenience functions / 便捷函数 ─────────────────────────────────────


def generate_resource_manifest(
    *,
    analysis_type: str,
    config: Mapping[str, Any],
    checksum: bool = False,
    checksum_directory_ids: Sequence[str] = (),
) -> ResourceManifest:
    """Create a ``ResourceManifest`` from a plugin config.

    Quick one-liner for plugin report writers:
        manifest = generate_resource_manifest(
            analysis_type=self.plugin_id,
            config=config,
            checksum=True,
        )
        manifest.write(result_dir / "provenance")
    """
    manifest = ResourceManifest(analysis_type=analysis_type)
    manifest.add_resources_from_config(
        config,
        checksum=checksum,
        checksum_directory_ids=checksum_directory_ids,
    )
    return manifest


def write_resource_manifest(
    output_dir: str | Path,
    *,
    analysis_type: str,
    config: Mapping[str, Any],
    checksum: bool = False,
    checksum_directory_ids: Sequence[str] = (),
) -> Path:
    """Generate and write a resource manifest in one call.

    Returns the path to the written manifest.
    """
    manifest = generate_resource_manifest(
        analysis_type=analysis_type,
        config=config,
        checksum=checksum,
        checksum_directory_ids=checksum_directory_ids,
    )
    return manifest.write(output_dir)


def checksum_file(path: str | Path, *, algorithm: str = "sha256") -> str:
    """Compute the hex digest of a file.

    Uses streaming reads to handle large files efficiently.
    """
    path = Path(path)
    if not path.is_file():
        return ""
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):  # 1 MiB chunks
            h.update(chunk)
    return h.hexdigest()


def checksum_path(path: str | Path) -> str:
    """Return a deterministic SHA-256 digest for a file or directory tree.

    Directory digests bind each relative file path to the SHA-256 of its
    contents.  Absolute paths, mtimes, permissions, and traversal order are
    deliberately excluded so the digest remains portable across machines.
    """
    root = Path(path)
    if root.is_file():
        return checksum_file(root)
    if not root.is_dir():
        return ""
    digest = hashlib.sha256()
    for item in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        relative = item.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(checksum_file(item).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


# ── Internal helpers / 内部辅助 ─────────────────────────────────────────


def _checksum_path(path: Path) -> str:
    """Compute checksum if *path* is a regular file, empty string otherwise."""
    if path.is_file():
        return checksum_file(path)
    return ""


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
