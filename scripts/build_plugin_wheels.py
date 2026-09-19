#!/usr/bin/env python3
"""Build the pinned abi-plugin submodule for ABI integration tests and containers.

Plugin source and packaging are maintained at https://github.com/sleepinlava/abi-plugin.
End users download individual wheels from that repository's GitHub Releases.
"""

from __future__ import annotations

import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_REPOSITORY = ROOT / "src" / "abi" / "plugins"
_builder_path = PLUGIN_REPOSITORY / "scripts" / "build_plugin_wheels.py"
if not _builder_path.is_file():
    raise RuntimeError("Initialize pinned plugins: git submodule update --init --recursive")
_builder = runpy.run_path(str(_builder_path))
PLUGINS = _builder["PLUGINS"]
PLUGIN_DEPENDENCIES = _builder["PLUGIN_DEPENDENCIES"]
PLASMID_SCRIPTS = _builder["PLASMID_SCRIPTS"]
core_version = _builder["core_version"]
stage_plugin = _builder["stage_plugin"]
write_pyproject = _builder["write_pyproject"]
build_wheel = _builder["build_wheel"]


def main() -> int:
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', metadata)
    if match is None or match.group(1) != core_version():
        raise SystemExit("Pinned abi-plugin VERSION must match ABI project.version")
    return int(_builder["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
