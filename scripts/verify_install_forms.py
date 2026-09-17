#!/usr/bin/env python3
"""WP11B acceptance: verify the three supported installation forms.

Installs the built wheels into fresh virtual environments and asserts:

1. core only         — no plugins are discoverable; an unknown analysis type
                        fails with an explainable error (no available types),
                        and self-contained historical results can still be
                        inspected, reported, and structurally validated.
2. core + one plugin — exactly that plugin is discoverable, dry-run works for
                        it, and other types remain clearly unknown.
3. core + full combo — every official plugin distribution resolves and each
                        plugin passes a light no-tool dry-run probe.

The script only reads the wheels and runs the packaged CLI; it never installs
environments, downloads databases, or runs real tools.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from email.parser import Parser
from pathlib import Path
from zipfile import BadZipFile, ZipFile

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
HISTORY_ANALYSIS_TYPE = "metagenomic_plasmid"


class InstallFormError(RuntimeError):
    """One installation form did not behave as accepted."""


def _subprocess_env() -> dict[str, str]:
    """Keep source checkout paths out of installed-wheel subprocesses."""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    return environment


def _run(command: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise InstallFormError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def _pip(venv_dir: Path, *arguments: str, cwd: Path, deps: bool = True) -> None:
    command = [str(venv_dir / "bin" / "python"), "-m", "pip", "install"]
    if not deps:
        command.append("--no-deps")
    command.append("--no-cache-dir")
    command.extend(arguments)
    _run(command, cwd=cwd)


def _abi(venv_dir: Path, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(venv_dir / "bin" / "abi"), *arguments],
        cwd=cwd,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
    )


def _wheel_metadata(wheel: Path) -> tuple[str, str, list[str]]:
    """Read the identity and runtime requirements from one wheel."""
    try:
        with ZipFile(wheel) as archive:
            metadata_paths = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_paths) != 1:
                raise InstallFormError(
                    f"wheel {wheel} must contain exactly one .dist-info/METADATA file"
                )
            payload = archive.read(metadata_paths[0]).decode("utf-8")
    except (OSError, BadZipFile, UnicodeDecodeError) as exc:
        raise InstallFormError(f"cannot read wheel metadata from {wheel}: {exc}") from exc

    metadata = Parser().parsestr(payload)
    name = str(metadata.get("Name") or "").strip()
    version = str(metadata.get("Version") or "").strip()
    requirements = [str(item).strip() for item in (metadata.get_all("Requires-Dist") or [])]
    if not name or not version:
        raise InstallFormError(f"wheel {wheel} has incomplete Name/Version metadata")
    return name, version, requirements


def validate_distribution_metadata(
    core_wheel: Path,
    plugin_wheels: dict[str, Path],
) -> str:
    """Require the core wheel and every plugin wheel to share one version."""
    core_name, core_version, _ = _wheel_metadata(core_wheel)
    if core_name != "abi-agent":
        raise InstallFormError(f"core wheel {core_wheel} declares unexpected name {core_name!r}")

    for expected_name, wheel in sorted(plugin_wheels.items()):
        plugin_name, plugin_version, requirements = _wheel_metadata(wheel)
        if plugin_name != expected_name:
            raise InstallFormError(
                f"plugin wheel {wheel} declares {plugin_name!r}, expected {expected_name!r}"
            )
        if plugin_version != core_version:
            raise InstallFormError(
                f"version mismatch: core abi-agent is {core_version}, "
                f"plugin {expected_name} is {plugin_version}"
            )
        normalized_requirements = {requirement.replace(" ", "") for requirement in requirements}
        expected_requirement = f"abi-agent=={core_version}"
        if expected_requirement not in normalized_requirements:
            raise InstallFormError(
                f"plugin {expected_name} must require {expected_requirement}, "
                f"found {requirements!r}"
            )
    return core_version


def _listed_types(venv_dir: Path, *, cwd: Path) -> list[str]:
    output = _run([str(venv_dir / "bin" / "abi"), "list-types"], cwd=cwd)
    rows = json.loads(output)
    return sorted(str(row["type"]) for row in rows)


def _dry_run(venv_dir: Path, plugin_id: str, workdir: Path) -> subprocess.CompletedProcess[str]:
    extra_arguments: list[str] = []
    if plugin_id == "metagenomic_plasmid":
        # This plugin requires an explicit sample even in dry-run mode.
        # The path is a planning fixture; --no-check-files avoids real data.
        sample_sheet = workdir / "plasmid-samples.tsv"
        sample_sheet.write_text(
            "sample_id\tplatform\tassembly\n"
            f"fixture\tassembly\t{workdir / 'fixture-contigs.fasta'}\n",
            encoding="utf-8",
        )
        extra_arguments = ["--sample-sheet", str(sample_sheet)]
    elif plugin_id == "wgs_bacannot":
        # Its external-workflow adapter also validates reads while producing
        # the dry-run summary. Supply tiny synthetic paired reads, not tools.
        reads = [workdir / f"fixture_R{pair}.fastq" for pair in (1, 2)]
        for pair, read in enumerate(reads, start=1):
            read.write_text(f"@fixture/{pair}\nACGT\n+\nIIII\n", encoding="utf-8")
        sample_sheet = workdir / "bacannot-samples.tsv"
        sample_sheet.write_text(
            f"sample_id\tplatform\tread1\tread2\nfixture\tillumina\t{reads[0]}\t{reads[1]}\n",
            encoding="utf-8",
        )
        extra_arguments = ["--sample-sheet", str(sample_sheet)]
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
        *extra_arguments,
        cwd=workdir,
    )


def _history_result_dir(
    root: Path,
    *,
    command_status: str = "success",
    run_status: str = "success",
    snapshot: str = "valid",
) -> Path:
    """Create a small self-contained historical result for core-only probing.

    The fixture intentionally uses only ABI's result-directory contract.  It
    contains no plugin code, tool output, plotting assets, or real input files.
    ``snapshot`` may be ``valid``, ``missing``, or ``invalid`` to exercise the
    honest degradation paths used by old and damaged result directories.
    """
    result_dir = root / f"history-{command_status}-{snapshot}"
    provenance = result_dir / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    (result_dir / "tables").mkdir()
    (result_dir / "execution_plan.json").write_text(
        json.dumps(
            {
                "analysis_type": HISTORY_ANALYSIS_TYPE,
                "project_name": "install-form-history",
                "steps": [],
                "selected_tools": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (provenance / "run_summary.json").write_text(
        json.dumps(
            {
                "analysis_type": HISTORY_ANALYSIS_TYPE,
                "status": run_status,
                "run_id": f"install-form-{command_status}",
                "plan_id": "install-form-plan",
                **(
                    {
                        "resumes_run_id": "install-form-previous",
                        "previous_run_archive": "provenance/archive/install-form-previous",
                    }
                    if command_status == "resumed"
                    else {}
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (provenance / "commands.tsv").write_text(
        "step_id\ttool_id\tcommand\tstatus\treason\n"
        f"history_step\tfixture\tfixture --{command_status}\t{command_status}\t"
        + ("fixture failure\n" if command_status == "failed" else "\n"),
        encoding="utf-8",
    )
    (provenance / "resolved_inputs.tsv").write_text(
        "step_id\tinput_name\tpath\texists\n", encoding="utf-8"
    )
    (provenance / "tool_versions.tsv").write_text("tool_id\tversion\tstatus\n", encoding="utf-8")
    (provenance / "resources.json").write_text("{}\n", encoding="utf-8")
    (provenance / "progress.jsonl").write_text("\n", encoding="utf-8")
    (result_dir / "tables" / "history.tsv").write_text("id\tvalue\nfixture\t1\n", encoding="utf-8")
    if snapshot == "valid":
        (provenance / "audit_snapshot.json").write_text(
            json.dumps(
                {
                    "schema_version": "abi.audit_snapshot.v1",
                    "analysis_type": HISTORY_ANALYSIS_TYPE,
                    "plugin_id": HISTORY_ANALYSIS_TYPE,
                    "report_title": "Historical ABI result",
                    "standard_table_schemas": {"history": ["id", "value"]},
                    "limitations": ["Core-only install did not run plugin validation."],
                    "references": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
    elif snapshot == "invalid":
        (provenance / "audit_snapshot.json").write_text(
            json.dumps(
                {
                    "schema_version": "abi.audit_snapshot.v0",
                    "analysis_type": HISTORY_ANALYSIS_TYPE,
                    "standard_table_schemas": {"history": ["id", "value"]},
                    "limitations": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
    elif snapshot != "missing":
        raise InstallFormError(f"unsupported history fixture snapshot mode: {snapshot!r}")
    return result_dir


def _json_result(result: subprocess.CompletedProcess[str], *, command: str) -> dict[str, object]:
    """Parse a successful ``--output-json`` CLI envelope."""
    if result.returncode != 0:
        raise InstallFormError(
            f"{command} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise InstallFormError(
            f"{command} did not return JSON:\n{result.stdout}\n{result.stderr}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise InstallFormError(f"{command} returned an unsuccessful envelope: {payload!r}")
    value = payload.get("result")
    if not isinstance(value, dict):
        raise InstallFormError(f"{command} response has no result object: {payload!r}")
    return value


def _probe_history_results(venv_dir: Path, root: Path) -> None:
    """Exercise core-only inspect/report/validate-result against old results."""
    fixtures = (
        ("success", "success", "valid"),
        ("failed", "failed", "valid"),
        ("resumed", "success", "valid"),
        ("success", "success", "missing"),
        ("success", "success", "invalid"),
    )
    for command_status, run_status, snapshot in fixtures:
        result_dir = _history_result_dir(
            root / "history",
            command_status=command_status,
            run_status=run_status,
            snapshot=snapshot,
        )
        inspected = _json_result(
            _abi(
                venv_dir,
                "inspect",
                "--result-dir",
                str(result_dir),
                "--output-json",
                cwd=root,
            ),
            command="inspect",
        )
        if inspected["audit_snapshot_status"] != snapshot:
            raise InstallFormError(
                f"inspect reported snapshot {inspected['audit_snapshot_status']!r}, "
                f"expected {snapshot!r} for {result_dir}"
            )
        if command_status == "failed" and not inspected["failed_steps"]:
            raise InstallFormError("inspect did not expose the failed historical step")
        if command_status == "resumed" and inspected["reused_steps"] != ["history_step"]:
            raise InstallFormError("inspect did not expose the resumed historical step")

        reported = _json_result(
            _abi(
                venv_dir,
                "report",
                "--result-dir",
                str(result_dir),
                "--output-json",
                cwd=root,
            ),
            command="report",
        )
        if reported["plugin_report_generated"] is not False:
            raise InstallFormError("core-only history report claimed plugin report generation")
        if reported["audit_snapshot_status"] != snapshot:
            raise InstallFormError(
                f"report reported snapshot {reported['audit_snapshot_status']!r}, "
                f"expected {snapshot!r}"
            )
        if not (result_dir / "report" / "report.md").is_file():
            raise InstallFormError(f"generic report was not written for {result_dir}")
        report_text = (result_dir / "report" / "report.md").read_text(encoding="utf-8")
        expected_command = f"fixture --{command_status}"
        if expected_command not in report_text:
            raise InstallFormError(f"generic report omitted the saved command {expected_command!r}")
        if command_status == "resumed" and (
            "Reused steps (validated resume)" not in report_text
            or "resumes run `install-form-previous`" not in report_text
        ):
            raise InstallFormError("generic report omitted the historical resume linkage")

        validated = _json_result(
            _abi(
                venv_dir,
                "validate-result",
                "--result-dir",
                str(result_dir),
                "--require-nonempty-tables",
                "--output-json",
                cwd=root,
            ),
            command="validate-result",
        )
        expected_valid = command_status != "failed" and snapshot == "valid"
        if validated["valid"] is not expected_valid:
            raise InstallFormError(
                f"validate-result returned valid={validated['valid']!r} for {result_dir}; "
                f"expected {expected_valid!r}"
            )
        if snapshot in {"missing", "invalid"} and validated["schema_source"] != "unavailable":
            raise InstallFormError(
                f"validate-result falsely resolved a schema for {snapshot} snapshot: {result_dir}"
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
        help="Developer-only offline fallback: use --system-site-packages and --no-deps; "
        "this mode is not a clean installation acceptance run.",
    )
    args = parser.parse_args()
    # Resolve before subprocesses move into their isolated working directories.
    args.dist_dir = args.dist_dir.resolve()
    args.plugin_dist_dir = args.plugin_dist_dir.resolve()

    def make_venv(path: Path) -> None:
        venv.EnvBuilder(
            with_pip=True,
            clear=True,
            system_site_packages=args.reuse_system_deps,
        ).create(path)

    def install(venv_dir: Path, wheels: list[Path]) -> None:
        _pip(
            venv_dir,
            *(str(wheel) for wheel in wheels),
            cwd=root,
            deps=not args.reuse_system_deps,
        )

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

    validate_distribution_metadata(core_wheel, plugin_wheels)

    with tempfile.TemporaryDirectory(prefix="abi-install-forms-") as tmp:
        root = Path(tmp)

        # ── Form 1: core only ────────────────────────────────────────
        core_only = root / "core-only"
        make_venv(core_only)
        install(core_only, [core_wheel])
        if not args.reuse_system_deps:
            _run(
                [
                    str(core_only / "bin" / "python"),
                    "-c",
                    "import importlib.util; "
                    "assert all(importlib.util.find_spec(name) is None "
                    "for name in ('numpy', 'pandas', 'scipy', 'matplotlib'))",
                ],
                cwd=root,
            )
        listed = _listed_types(core_only, cwd=root)
        if listed != []:
            raise InstallFormError(f"core-only install must list no plugins, got {listed!r}")
        result = _dry_run(core_only, PROBE_PLUGIN, root)
        _assert_unknown_type_message(result, available=[])
        _probe_history_results(core_only, root)
        print(
            "[1/3] core only: no plugins discoverable; unknown types and historical "
            "results degrade honestly"
        )

        # ── Form 2: core + one plugin ─────────────────────────────────
        single = root / "single-plugin"
        make_venv(single)
        install(
            single,
            [core_wheel, plugin_wheels[OFFICIAL_PLUGINS[SINGLE_FORM_PLUGIN]]],
        )
        listed = _listed_types(single, cwd=root)
        if listed != [SINGLE_FORM_PLUGIN]:
            raise InstallFormError(
                f"single-plugin install must list only {SINGLE_FORM_PLUGIN!r}, got {listed!r}"
            )
        single_probe_dir = root / "single-plugin-probes"
        single_probe_dir.mkdir()
        _run(
            [
                str(single / "bin" / "python"),
                "-c",
                "import pandas as pd; "
                "from abi.plugins.rnaseq_expression.scripts.run_enrichment import bh_adjust; "
                "assert abs(bh_adjust(pd.Series([0.01, 0.04])).iloc[0] - 0.02) < 1e-12",
            ],
            cwd=root,
        )
        result = _dry_run(single, SINGLE_FORM_PLUGIN, single_probe_dir)
        if result.returncode != 0:
            raise InstallFormError(
                f"dry-run of the installed plugin failed:\n{result.stdout}\n{result.stderr}"
            )
        result = _dry_run(single, PROBE_PLUGIN, single_probe_dir)
        _assert_unknown_type_message(result, available=[SINGLE_FORM_PLUGIN])
        print(f"[2/3] core + {SINGLE_FORM_PLUGIN}: selected plugin dry-runs; others stay unknown")

        # EasyMeta must resolve its NumPy dependency independently of RNA-seq.
        easymeta = root / "single-easymetagenome"
        make_venv(easymeta)
        install(easymeta, [core_wheel, plugin_wheels[OFFICIAL_PLUGINS["easymetagenome"]]])
        if _listed_types(easymeta, cwd=root) != ["easymetagenome"]:
            raise InstallFormError("EasyMeta standalone install discovered unexpected plugins")
        _run(
            [
                str(easymeta / "bin" / "python"),
                "-c",
                "from abi.plugins.easymetagenome.reproduction import _spearman; "
                "assert abs(_spearman([1., 2., 3.], [2., 4., 6.]) - 1.) < 1e-12",
            ],
            cwd=root,
        )
        easymeta_probe_dir = root / "single-easymetagenome-probes"
        easymeta_probe_dir.mkdir()
        result = _dry_run(easymeta, "easymetagenome", easymeta_probe_dir)
        if result.returncode:
            raise InstallFormError(f"EasyMeta standalone dry-run failed: {result.stderr}")
        print("[2/3] core + easymetagenome: standalone statistics and dry-run passed")

        # ── Form 3: core + full official combo ────────────────────────
        combo = root / "full-combo"
        make_venv(combo)
        install(
            combo,
            [core_wheel, *(path for path in plugin_wheels.values())],
        )
        listed = _listed_types(combo, cwd=root)
        expected = sorted(OFFICIAL_PLUGINS)
        if listed != expected:
            raise InstallFormError(f"full combo must list {expected!r}, got {listed!r}")
        combo_probe_dir = root / "full-combo-probes"
        combo_probe_dir.mkdir()
        for plugin_id in expected:
            result = _dry_run(combo, plugin_id, combo_probe_dir)
            if result.returncode != 0:
                raise InstallFormError(
                    f"full-combo dry-run of {plugin_id} failed:\n{result.stdout}\n{result.stderr}"
                )
        print("[3/3] core + full official combo: every plugin resolves and dry-runs")

    print("install-form acceptance passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InstallFormError as exc:
        print(f"install-form acceptance FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
