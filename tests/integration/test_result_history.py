from __future__ import annotations

import json
from pathlib import Path

from abi.agent import ABIAgentInterface
from abi.results import validate_abi_result_dir


def test_local_rerun_archives_previous_result_bundle_and_snapshot(tmp_path: Path) -> None:
    outdir = tmp_path / "results"
    agent = ABIAgentInterface()

    first = json.loads(
        agent.run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            confirm_execution=True,
            check_files=False,
        )
    )
    assert first["status"] == "success"
    first_summary = json.loads(
        (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )
    tracked = [
        Path("execution_plan.json"),
        Path("execution_plan.resolved.json"),
        Path("provenance/audit_snapshot.json"),
        Path("report/report.md"),
        Path("report/report.html"),
        *sorted(path.relative_to(outdir) for path in (outdir / "tables").glob("*.tsv")),
    ]
    before = {relative: (outdir / relative).read_bytes() for relative in tracked}

    second = json.loads(
        agent.run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            confirm_execution=True,
            check_files=False,
        )
    )
    assert second["status"] == "success"
    second_summary = json.loads(
        (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert second_summary["previous_run_archive"]

    archive = outdir / "provenance" / second_summary["previous_run_archive"]
    for relative, content in before.items():
        assert (archive / relative).read_bytes() == content
    assert (
        json.loads((archive / "provenance/run_summary.json").read_text(encoding="utf-8"))["run_id"]
        == first_summary["run_id"]
    )
    assert validate_abi_result_dir(archive)["valid"] is True
    assert (outdir / "provenance/audit_snapshot.json").is_file()
