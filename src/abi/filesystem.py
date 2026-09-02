"""Filesystem helpers used by ABI runtimes.

This module is a dependency-free leaf: it must not import other ``abi``
modules beyond ``abi.errors`` so that the canonical checksum utilities can
be used from anywhere in the package without import cycles (P1-4).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from abi.errors import ABIError

__all__ = ["checksum_file", "checksum_path", "ensure_directory", "ensure_parent"]


def checksum_file(path: str | Path, *, algorithm: str = "sha256") -> str:
    """Compute the hex digest of a file.

    Uses streaming reads to handle large files efficiently.
    Returns ``""`` when *path* is not an existing regular file.
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


def ensure_directory(path: str | Path, *, label: str = "Directory") -> Path:
    """Return an existing directory or create it when missing."""
    directory = Path(path)
    if directory.exists():
        if not directory.is_dir():
            raise ABIError(f"{label} exists but is not a directory: {directory}")
        return directory
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def ensure_parent(path: str | Path) -> Path:
    """Create a path's parent directory and return the path unchanged."""
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
