#!/usr/bin/env python3
"""Verify Linux capability metadata emitted by an installed ABI wheel."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ARCHITECTURES = {"x86_64", "aarch64"}
ALLOWED_STATUSES = {"certified", "partial", "unsupported"}
ENVIRONMENTS = {
    "abi-qc",
    "abi-stats",
    "amplicon",
    "autoplasm-abundance",
    "autoplasm-annotation",
    "autoplasm-assembly",
    "autoplasm-base",
    "autoplasm-checkm2",
    "autoplasm-integronfinder",
    "autoplasm-nextflow",
    "autoplasm-plasmid-binning",
    "autoplasm-plasmid-detect",
    "autoplasm-qc",
    "autoplasm-rgi",
    "autoplasm-scapp",
    "autoplasm-visualization",
    "easymeta-humann",
    "easymeta-p0",
    "rnaseq",
    "stats",
    "wgs",
}
PLUGINS = {
    "amplicon_16s",
    "easymetagenome",
    "metagenomic_plasmid",
    "metatranscriptomics",
    "rnaseq_expression",
    "viral_viwrap",
    "wgs_bacteria",
}


class CapabilityVerificationError(RuntimeError):
    """Raised when installed-wheel capability evidence is malformed."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CapabilityVerificationError(f"{label} must be an object")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CapabilityVerificationError(f"{label} must be a list")
    if not all(isinstance(item, str) for item in value):
        raise CapabilityVerificationError(f"{label} must contain only strings")
    return list(value)


def _validate_cell(cell: Any, label: str) -> None:
    payload = _mapping(cell, label)
    status = payload.get("status")
    if status not in ALLOWED_STATUSES:
        raise CapabilityVerificationError(f"{label} has invalid status: {status!r}")
    blockers = _string_list(payload.get("blockers"), f"{label}.blockers")
    alternatives = _string_list(payload.get("alternatives"), f"{label}.alternatives")
    evidence = _string_list(payload.get("evidence"), f"{label}.evidence")
    if not evidence:
        raise CapabilityVerificationError(f"{label}.evidence must not be empty")
    if status in {"partial", "unsupported"} and not blockers:
        raise CapabilityVerificationError(f"{label}.blockers must not be empty")
    if status in {"partial", "unsupported"} and not alternatives:
        raise CapabilityVerificationError(f"{label}.alternatives must not be empty")


def validate_capability_report(report: Any, *, architecture: str) -> None:
    """Validate the complete installed-wheel capability matrix."""

    payload = _mapping(report, "report")
    platform = _mapping(payload.get("platform"), "report.platform")
    if platform.get("system") != "Linux":
        raise CapabilityVerificationError("report.platform.system must be Linux")
    if platform.get("normalized_architecture") != architecture:
        raise CapabilityVerificationError(
            "runner architecture mismatch: "
            f"expected {architecture}, got {platform.get('normalized_architecture')!r}"
        )

    support = _mapping(payload.get("support"), "report.support")
    if support.get("active_os") != "linux":
        raise CapabilityVerificationError("report.support.active_os must be linux")
    if support.get("allowed_statuses") != ["certified", "partial", "unsupported"]:
        raise CapabilityVerificationError("report.support.allowed_statuses is invalid")
    declared_architectures = _mapping(
        support.get("architectures"),
        "report.support.architectures",
    )
    if set(declared_architectures) != ARCHITECTURES:
        raise CapabilityVerificationError(
            "report.support.architectures must declare x86_64 and aarch64"
        )

    for scope, expected_names in (("environments", ENVIRONMENTS), ("plugins", PLUGINS)):
        matrix = _mapping(support.get(scope), f"report.support.{scope}")
        if set(matrix) != expected_names:
            missing = sorted(expected_names - set(matrix))
            extra = sorted(set(matrix) - expected_names)
            raise CapabilityVerificationError(
                f"{scope} names differ; missing={missing}, extra={extra}"
            )
        for name, raw_cells in matrix.items():
            cells = _mapping(raw_cells, f"{scope}.{name}")
            if set(cells) != ARCHITECTURES:
                raise CapabilityVerificationError(
                    f"{name} architectures must be x86_64 and aarch64"
                )
            for cell_architecture, cell in cells.items():
                _validate_cell(cell, f"{scope}.{name}.{cell_architecture}")

    viwrap = _mapping(
        _mapping(support["plugins"]["viral_viwrap"], "plugins.viral_viwrap"),
        "plugins.viral_viwrap",
    )
    if any(
        _mapping(viwrap[cell_architecture], f"plugins.viral_viwrap.{cell_architecture}").get(
            "status"
        )
        != "unsupported"
        for cell_architecture in ARCHITECTURES
    ):
        raise CapabilityVerificationError(
            "viral_viwrap must remain unsupported on x86_64 and aarch64"
        )


def _run_json(command: list[str], *, expected_returncode: int) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != expected_returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise CapabilityVerificationError(
            f"command returned {completed.returncode}, expected {expected_returncode}: "
            f"{' '.join(command)}: {detail}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CapabilityVerificationError(
            f"command did not emit valid JSON: {' '.join(command)}"
        ) from exc
    return dict(_mapping(payload, "command output"))


def verify_installed_wheel(
    *,
    abi_executable: Path,
    mamba_root: Path,
    architecture: str,
    output: Path,
    unsupported_plugin: str,
) -> None:
    """Exercise installed-wheel discovery and fail-closed plugin diagnostics."""

    if architecture not in ARCHITECTURES:
        raise CapabilityVerificationError(f"unsupported expected architecture: {architecture}")
    if not abi_executable.is_file():
        raise CapabilityVerificationError(f"ABI executable does not exist: {abi_executable}")
    mamba_root.mkdir(parents=True, exist_ok=True)
    report = _run_json(
        [
            str(abi_executable),
            "env",
            "discover",
            "--mamba-root",
            str(mamba_root),
            "--output-json",
        ],
        expected_returncode=0,
    )
    validate_capability_report(report, architecture=architecture)

    doctor = _run_json(
        [
            str(abi_executable),
            "env",
            "doctor",
            "--type",
            unsupported_plugin,
            "--mamba-root",
            str(mamba_root),
            "--output-json",
        ],
        expected_returncode=1,
    )
    plugin = _mapping(doctor.get("plugin"), "doctor.plugin")
    if plugin.get("analysis_type") != unsupported_plugin:
        raise CapabilityVerificationError("doctor report contains the wrong plugin")
    if plugin.get("status") != "unsupported":
        raise CapabilityVerificationError(f"{unsupported_plugin} doctor status must be unsupported")
    expected_issue = f"unsupported_plugin:{unsupported_plugin}:{architecture}"
    if expected_issue not in doctor.get("issues", []):
        raise CapabilityVerificationError(f"doctor report is missing issue: {expected_issue}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Linux capabilities emitted by an installed ABI wheel."
    )
    parser.add_argument("--abi", required=True, type=Path, help="Installed ABI executable.")
    parser.add_argument("--mamba-root", required=True, type=Path)
    parser.add_argument("--architecture", required=True, choices=sorted(ARCHITECTURES))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--unsupported-plugin", default="viral_viwrap")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        verify_installed_wheel(
            abi_executable=args.abi,
            mamba_root=args.mamba_root,
            architecture=args.architecture,
            output=args.output,
            unsupported_plugin=args.unsupported_plugin,
        )
    except (CapabilityVerificationError, OSError, subprocess.SubprocessError) as exc:
        print(f"Linux wheel capability verification failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Linux wheel capability verification passed: {args.architecture}, "
        f"{len(ENVIRONMENTS)} environments, {len(PLUGINS)} plugins"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
