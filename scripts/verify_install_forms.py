#!/usr/bin/env python3
"""WP11B acceptance: verify the three supported installation forms.

Installs the built wheels into fresh virtual environments and asserts:

1. core only         — no plugins are discoverable; an unknown analysis type
                        fails with an explainable error (no available types).
2. core + one plugin — exactly that plugin is discoverable, dry-run works for
                        it, and other types remain clearly unknown.
3. core + full combo — every official plugin distribution resolves.

The script only reads the wheels and runs the packaged CLI; it never installs
environments, downloads databases, or runs real tools.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

OFFICIAL_PLUGINS: dict[str, str] = {
    "amplicon_16s": "abi-agent-plugin-amplicon-16s",
    "easymetagenome": "abi-agent-plugin-easymetagenome",
    "metagenomic_plasmid": "abi-agent-plugin-metagenomic-plasmid",
    "metatranscriptomics": "abi-agent-plugin-metatranscriptomics",
    "rnaseq_expression": "abi-agent-plugin-rnaseq-expression",
    "viral_viwrap": "abi-agent-plugin-viral-viwrap",
    "wgs_bacannot": "abi-agent-plugin-wgs-bacannot",
    "wgs_bacteria": "abi-agent-plugin-wgs-bacteria",
}

# Light plugin whose configless dry-run is exercised by CI's all-plugins smoke.
SINGLE_FORM_PLUGIN = "rnaseq_expression"
PROBE_PLUGIN = "metagenomic_plasmid"


class InstallFormError(RuntimeError):
    """One installation form did not behave as accepted."""


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise InstallFormError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def _pip(venv_dir: Path, *arguments: str, deps: bool = True) -> None:
    command = [str(venv_dir / "bin" / "python"), "-m", "pip", "install"]
    if not deps:
        command.append("--no-deps")
    command.append("--no-cache-dir")
    command.extend(arguments)
    _run(command)


def _abi(venv_dir: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(venv_dir / "bin" / "abi"), *arguments],
        capture_output=True,
        text=True,
    )


def _listed_types(venv_dir: Path) -> list[str]:
    output = _run([str(venv_dir / "bin" / "abi"), "list-types"])
    rows = json.loads(output)
    return sorted(str(row["type"]) for row in rows)


def _dry_run(venv_dir: Path, plugin_id: str, workdir: Path) -> subprocess.CompletedProcess[str]:
    return _abi(
        venv_dir,
        "dry-run",
        "--type",
        plugin_id,
        "--outdir",
        str(workdir / f"out-{plugin_id}"),
        "--log-dir",
        str(workdir / f"log-{plugin_id}"),
        "--no-check-files",
        "--no-progress",
    )


def _assert_unknown_type_message(
    result: subprocess.CompletedProcess[str], *, available: list[str]
) -> None:
    combined = result.stdout + result.stderr
    if result.returncode == 0:
        raise InstallFormError(f"unknown analysis type unexpectedly succeeded:\n{combined}")
    if "unknown_analysis_type" not in combined or "Unknown ABI analysis type" not in combined:
        raise InstallFormError(f"unknown analysis type error is not explainable:\n{combined}")
    if f"Available: {available!r}" not in combined and str(sorted(available)) not in combined:
        raise InstallFormError(
            f"unknown analysis type error does not list available types {available!r}:\n{combined}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist-dir",
        type=Path,
        required=True,
        help="Directory containing the core abi_agent-*.whl.",
    )
    parser.add_argument(
        "--plugin-dist-dir",
        type=Path,
        required=True,
        help="Directory containing the abi_agent_plugin_*.whl wheels.",
    )
    parser.add_argument(
        "--reuse-system-deps",
        action="store_true",
        help="Offline fallback: create --system-site-packages venvs and install wheels with "
        "--no-deps. CI runs without this flag so every form gets clean dependency resolution.",
    )
    args = parser.parse_args()

    def make_venv(path: Path) -> None:
        venv.EnvBuilder(
            with_pip=True,
            clear=True,
            system_site_packages=args.reuse_system_deps,
        ).create(path)

    def install(venv_dir: Path, wheels: list[Path]) -> None:
        _pip(venv_dir, *(str(wheel) for wheel in wheels), deps=not args.reuse_system_deps)

    core_wheels = sorted(args.dist_dir.glob("abi_agent-*.whl"))
    if len(core_wheels) != 1:
        raise InstallFormError(f"expected exactly one core wheel in {args.dist_dir}: {core_wheels}")
    core_wheel = core_wheels[0]
    plugin_wheels: dict[str, Path] = {}
    for dist in OFFICIAL_PLUGINS.values():
        matches = sorted(args.plugin_dist_dir.glob(f"{dist.replace('-', '_')}-*.whl"))
        if len(matches) != 1:
            raise InstallFormError(
                f"expected exactly one wheel for {dist!r} in {args.plugin_dist_dir}: {matches}"
            )
        plugin_wheels[dist] = matches[0]

    with tempfile.TemporaryDirectory(prefix="abi-install-forms-") as tmp:
        root = Path(tmp)

        # ── Form 1: core only ────────────────────────────────────────
        core_only = root / "core-only"
        make_venv(core_only)
        install(core_only, [core_wheel])
        listed = _listed_types(core_only)
        if listed != []:
            raise InstallFormError(f"core-only install must list no plugins, got {listed!r}")
        result = _dry_run(core_only, PROBE_PLUGIN, root)
        _assert_unknown_type_message(result, available=[])
        print("[1/3] core only: no plugins discoverable; unknown type errors explainably")

        # ── Form 2: core + one plugin ─────────────────────────────────
        single = root / "single-plugin"
        make_venv(single)
        install(
            single,
            [core_wheel, plugin_wheels[OFFICIAL_PLUGINS[SINGLE_FORM_PLUGIN]]],
        )
        listed = _listed_types(single)
        if listed != [SINGLE_FORM_PLUGIN]:
            raise InstallFormError(
                f"single-plugin install must list only {SINGLE_FORM_PLUGIN!r}, got {listed!r}"
            )
        result = _dry_run(single, SINGLE_FORM_PLUGIN, root)
        if result.returncode != 0:
            raise InstallFormError(
                f"dry-run of the installed plugin failed:\n{result.stdout}\n{result.stderr}"
            )
        result = _dry_run(single, PROBE_PLUGIN, root)
        _assert_unknown_type_message(result, available=[SINGLE_FORM_PLUGIN])
        print(f"[2/3] core + {SINGLE_FORM_PLUGIN}: selected plugin dry-runs; others stay unknown")

        # ── Form 3: core + full official combo ────────────────────────
        combo = root / "full-combo"
        make_venv(combo)
        install(
            combo,
            [core_wheel, *(path for path in plugin_wheels.values())],
        )
        listed = _listed_types(combo)
        expected = sorted(OFFICIAL_PLUGINS)
        if listed != expected:
            raise InstallFormError(f"full combo must list {expected!r}, got {listed!r}")
        print("[3/3] core + full official combo: every plugin resolves")

    print("install-form acceptance passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InstallFormError as exc:
        print(f"install-form acceptance FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
