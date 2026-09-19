#!/usr/bin/env python3
"""Verify the exact release distribution set, identities and SHA-256 manifest.

Run --write-manifest once on the built artifacts. Run without that flag on the
downloaded GitHub Release assets before publishing the identical bytes to PyPI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from email.parser import Parser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_install_forms import (  # noqa: E402
    OFFICIAL_PLUGINS,
    InstallFormError,
    validate_distribution_metadata,
)

MANIFEST = "release-artifacts.json"


def distribution_manifest(directory: Path, version: str) -> dict[str, object]:
    """Validate identities before hashing; never extract untrusted archives."""
    names = ["abi-agent", *OFFICIAL_PLUGINS.values()]
    wheels = {
        name: directory / f"{name.replace('-', '_')}-{version}-py3-none-any.whl" for name in names
    }
    sdist = directory / f"abi_agent-{version}.tar.gz"
    expected = {path.name for path in wheels.values()} | {sdist.name}
    actual = {
        path.name for path in directory.iterdir() if path.name.endswith((".whl", ".tar.gz", ".zip"))
    }
    if actual != expected:
        raise InstallFormError(
            f"distribution set mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    for name in expected:
        if not (directory / name).is_file() or (directory / name).is_symlink():
            raise InstallFormError(f"distribution must be a regular file: {name}")
    core = wheels.pop("abi-agent")
    if validate_distribution_metadata(core, wheels) != version:
        raise InstallFormError(f"release version must be {version}")
    try:
        with tarfile.open(sdist, "r:gz") as archive:
            entries = [
                item
                for item in archive.getmembers()
                if item.name == f"abi_agent-{version}/PKG-INFO"
            ]
            if len(entries) != 1 or not entries[0].isfile():
                raise InstallFormError("sdist must have one top-level PKG-INFO")
            stream = archive.extractfile(entries[0])
            if stream is None:
                raise InstallFormError("cannot read sdist PKG-INFO")
            metadata = Parser().parsestr(stream.read().decode("utf-8"))
            if metadata.get("Name") != "abi-agent" or metadata.get("Version") != version:
                raise InstallFormError("sdist identity does not match release")
    except (tarfile.TarError, UnicodeDecodeError) as exc:
        raise InstallFormError(f"invalid sdist: {exc}") from exc
    return {
        "schema_version": 1,
        "version": version,
        "sha256": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in sorted(expected)
        },
    }


def verify_release(directory: Path, version: str, *, write_manifest: bool = False) -> None:
    expected = distribution_manifest(directory, version)
    manifest = directory / MANIFEST
    if write_manifest:
        # Existing manifests are release identities, never silently replaced.
        with manifest.open("x", encoding="utf-8") as handle:
            json.dump(expected, handle, indent=2, sort_keys=True)
            handle.write("\n")
    else:
        actual = json.loads(manifest.read_text(encoding="utf-8"))
        if actual != expected:
            raise InstallFormError("release manifest mismatch: identity or artifact bytes changed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--tag", required=True, help="Verified release tag, v<version>")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    if not args.tag.startswith("v") or not args.tag[1:] or "/" in args.tag:
        raise InstallFormError("expected a v<version> release tag")
    verify_release(args.dist_dir, args.tag[1:], write_manifest=args.write_manifest)
    print(f"Release artifacts verified: {args.tag}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (InstallFormError, OSError, ValueError) as exc:
        print(f"Release verification FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
