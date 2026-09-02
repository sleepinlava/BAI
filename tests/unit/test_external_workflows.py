from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from abi.external_workflows.evidence import archive_evidence_files, verify_evidence_manifest
from abi.external_workflows.models import ExternalTaskAttempt
from abi.external_workflows.nextflow import import_nextflow_trace, write_task_attempts_tsv
from abi.plugins import get_plugin
from abi.runtimes.base import RuntimeOptions
from abi.runtimes.nextflow import NextflowRuntime
from abi.schemas import ABIError


def test_nextflow_import_preserves_every_task_attempt(tmp_path: Path) -> None:
    trace = tmp_path / "trace.tsv"
    trace.write_text(
        "task_id\thash\tprocess\ttag\tattempt\tstatus\texit\texecutor\tnative_id\tworkdir\n"
        "1\taa/111\tBACANNOT:ASSEMBLY:UNICYCLER\tS1\t1\tFAILED\t137\tslurm\t9001\twork/aa/111\n"
        "2\tbb/222\tBACANNOT:ASSEMBLY:UNICYCLER\tS1\t2\tCOMPLETED\t0\tslurm\t9002\twork/bb/222\n"
        "3\tcc/333\tBACANNOT:ASSEMBLY:UNICYCLER\tS2\t1\tCACHED\t0\tslurm\t9003\twork/cc/333\n",
        encoding="utf-8",
    )

    attempts = import_nextflow_trace(
        trace,
        external_workflow_id="run-1",
        process_mapper=lambda name: "assembly" if "UNICYCLER" in name else "unmapped",
    )

    assert [(row.sample_id, row.attempt, row.status) for row in attempts] == [
        ("S1", 1, "FAILED"),
        ("S1", 2, "COMPLETED"),
        ("S2", 1, "CACHED"),
    ]
    assert attempts[0].native_id == "9001"
    assert attempts[0].raw_trace_row_sha256

    output = write_task_attempts_tsv(attempts, tmp_path / "task_attempts.tsv")
    assert output.read_text(encoding="utf-8").count("\n") == 4


def test_evidence_manifest_detects_raw_evidence_tampering(tmp_path: Path) -> None:
    source = tmp_path / "nextflow_trace.tsv"
    source.write_text("task_id\tstatus\n1\tCOMPLETED\n", encoding="utf-8")

    manifest_path = archive_evidence_files(
        [(source, "nextflow_trace")],
        tmp_path / "bundle",
        collector_version="test-v1",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archived = manifest_path.parent / manifest["files"][0]["path"]
    archived.write_text("tampered\n", encoding="utf-8")

    verification = verify_evidence_manifest(manifest_path)

    assert verification["valid"] is False
    assert verification["errors"][0]["code"] == "checksum_mismatch"


def test_archived_manifest_is_verifiable_by_both_implementations(tmp_path: Path) -> None:
    """The bundle manifest must carry the canonical "artifacts" key so the core
    verifier (abi.evidence) and the external verifier agree on the same bytes
    (P0-1: eliminate the dual vacuously-valid manifest formats)."""
    from abi.evidence import verify_evidence_manifest as verify_core_evidence_manifest

    source = tmp_path / "nextflow_trace.tsv"
    source.write_text("task_id\tstatus\n1\tCOMPLETED\n", encoding="utf-8")

    manifest_path = archive_evidence_files(
        [(source, "nextflow_trace")],
        tmp_path / "bundle",
        collector_version="test-v1",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifacts"][0]["path"] == manifest["files"][0]["path"]
    assert manifest["artifacts"][0]["sha256"] == manifest["files"][0]["sha256"]

    external = verify_evidence_manifest(manifest_path)
    core = verify_core_evidence_manifest(manifest_path)
    assert external["valid"] is True
    assert core.valid is True
    assert core.checked == 1


def test_external_verify_rejects_empty_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "evidence_manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": "abi.evidence-manifest.v1", "complete": True}),
        encoding="utf-8",
    )

    result = verify_evidence_manifest(manifest)

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "empty_manifest"


def test_managed_nextflow_run_writes_attempt_and_raw_evidence(tmp_path: Path) -> None:
    fake = tmp_path / "nextflow"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "def write_after(flag, text):\n"
        "    if flag in args:\n"
        "        path = pathlib.Path(args[args.index(flag) + 1])\n"
        "        path.parent.mkdir(parents=True, exist_ok=True)\n"
        "        path.write_text(text)\n"
        "write_after('-with-trace', "
        "'task_id\\thash\\tprocess\\ttag\\tattempt\\tstatus\\texit\\tworkdir\\n'"
        "+ '1\\taa/111\\tBACANNOT:UNICYCLER\\tS1\\t1\\tCOMPLETED\\t0\\twork/aa/111\\n'"
        "+ '2\\tbb/222\\tBACANNOT:PROKKA\\tS1\\t1\\tCOMPLETED\\t0\\twork/bb/222\\n'"
        "+ '3\\tcc/333\\tBACANNOT:MLST\\tS1\\t1\\tCACHED\\t0\\twork/cc/333\\n'"
        "+ '4\\tdd/444\\tBACANNOT:AMRFINDER\\tS1\\t1\\tCOMPLETED\\t0\\twork/dd/444\\n')\n"
        "write_after('-with-report', '<html>report</html>')\n"
        "write_after('-with-timeline', '<html>timeline</html>')\n"
        "write_after('-with-dag', '<html>dag</html>')\n"
        "write_after('-log', 'nextflow log')\n"
        "out = pathlib.Path(args[args.index('--output') + 1])\n"
        "(out / 'S1/assembly/unicycler_S1').mkdir(parents=True, exist_ok=True)\n"
        "(out / 'S1/assembly/unicycler_S1/assembly.fasta').write_text('>c1\\nACGTACGT\\n')\n"
        "(out / 'S1/annotation').mkdir(parents=True, exist_ok=True)\n"
        "(out / 'S1/annotation/S1.fna').write_text('>c1\\nACGTACGT\\n')\n"
        "(out / 'S1/annotation/S1.gff').write_text("
        "'c1\\tProkka\\tCDS\\t1\\t8\\t.\\t+\\t0\\tID=x;product=p\\n')\n"
        "(out / 'S1/MLST').mkdir(parents=True, exist_ok=True)\n"
        "(out / 'S1/MLST/S1_mlst_analysis.txt').write_text("
        "'S1.fna\\tsaureus\\t93\\t1\\t2\\t3\\t4\\t5\\t6\\t7\\n')\n"
        "(out / 'S1/resistance/AMRFinderPlus').mkdir(parents=True, exist_ok=True)\n"
        "amr = out / 'S1/resistance/AMRFinderPlus/AMRFinder_resistance-only.tsv'\n"
        "amr.write_text("
        "'Protein identifier\\tGene symbol\\tElement subtype\\tClass\\tMethod\\t'"
        "+ '% Identity to reference sequence\\t% Coverage of reference sequence\\n'"
        "+ 'p1\\tmecA\\tAMR\\tbeta-lactam\\tBLASTP\\t100\\t100\\n')\n"
        "work = pathlib.Path(args[args.index('-work-dir') + 1])\n"
        "for task_hash in ('aa/111', 'bb/222', 'cc/333', 'dd/444'):\n"
        "    task = work / task_hash\n"
        "    task.mkdir(parents=True, exist_ok=True)\n"
        "    (task / '.command.sh').write_text('#!/bin/sh\\ntrue\\n')\n"
        "    (task / '.command.out').write_text('ok\\n')\n"
        "    (task / '.command.err').write_text('')\n"
        "    (task / '.exitcode').write_text('0\\n')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    read1 = tmp_path / "S1_R1.fastq.gz"
    read2 = tmp_path / "S1_R2.fastq.gz"
    read1.write_bytes(gzip.compress(b"@r1\nACGT\n+\nFFFF\n"))
    read2.write_bytes(gzip.compress(b"@r2\nTGCA\n+\nFFFF\n"))
    sheet = tmp_path / "samples.tsv"
    sheet.write_text(
        f"sample_id\tplatform\tread1\tread2\nS1\tillumina\t{read1}\t{read2}\n",
        encoding="utf-8",
    )
    database = tmp_path / "db"
    database.mkdir()
    plugin = get_plugin("wgs_bacannot")
    config = plugin.load_config(
        overrides={
            "outdir": str(tmp_path / "result"),
            "input": {"sample_sheet": str(sheet)},
            "resources": {"bacannot_db": str(database)},
        }
    )
    plan = plugin.build_plan(config)
    runtime = NextflowRuntime(
        plugin,
        options=RuntimeOptions(engine="nextflow", nextflow_bin=fake, smoke=True),
    )

    result = runtime.run(plan, config)

    assert result.status == "success"
    attempts = result.outputs["task_attempts"].read_text(encoding="utf-8")
    assert attempts.count("\n") == 5
    assert "CACHED" in attempts
    assert "task-1-attempt-1/.command.sh" in attempts
    assert verify_evidence_manifest(result.outputs["evidence_manifest"])["valid"] is True
    snapshot = json.loads(result.outputs["external_plan_snapshot"].read_text(encoding="utf-8"))
    assert snapshot["workflow"]["commit_sha"] == "a78ddb0bffe75139adf1f443260d6d5b1987fe27"
    assert (Path(config["outdir"]) / "standard" / "mlst_profile.tsv").is_file()
    assert "mecA" in (Path(config["outdir"]) / "standard" / "amr_profile.tsv").read_text()
    assert json.loads((Path(config["outdir"]) / "validation.json").read_text())["valid"] is True


def test_bacannot_validation_fails_when_required_process_is_missing(tmp_path: Path) -> None:
    result = tmp_path / "result"
    provenance = result / "provenance"
    raw_trace = tmp_path / "trace.tsv"
    raw_trace.write_text("task_id\tstatus\n1\tCOMPLETED\n", encoding="utf-8")
    archive_evidence_files(
        [(raw_trace, "nextflow_trace")],
        provenance,
        collector_version="test-v1",
    )
    write_task_attempts_tsv(
        [
            ExternalTaskAttempt(
                external_workflow_id="run-1",
                task_id="1",
                task_hash="aa/111",
                process_name="BACANNOT:UNICYCLER",
                process_class="assembly",
                sample_id="S1",
                attempt=1,
                status="COMPLETED",
            )
        ],
        provenance / "task_attempts.tsv",
    )
    (provenance / "external_plan_snapshot.json").write_text(
        json.dumps(
            {
                "inputs": [{"sample_id": "S1", "role": "read1"}],
                "modules": {"assembly": True, "annotation": True, "mlst": True, "amr": True},
            }
        ),
        encoding="utf-8",
    )

    validation = get_plugin("wgs_bacannot").validate_result_dir(result)

    assert validation["valid"] is False
    missing = [row for row in validation["errors"] if row.get("status") == "missing_process"]
    assert {row["contract_id"] for row in missing} >= {
        "bacannot_annotation",
        "bacannot_mlst",
        "bacannot_amr",
    }


def test_validation_uses_snapshot_samples_and_marks_disabled_amr_not_selected(
    tmp_path: Path,
) -> None:
    result = tmp_path / "result"
    provenance = result / "provenance"
    trace = tmp_path / "trace.tsv"
    trace.write_text("task_id\tstatus\n", encoding="utf-8")
    archive_evidence_files([(trace, "nextflow_trace")], provenance, collector_version="test-v1")
    write_task_attempts_tsv([], provenance / "task_attempts.tsv")
    (provenance / "external_plan_snapshot.json").write_text(
        json.dumps(
            {
                "inputs": [{"sample_id": "S1", "role": "read1"}],
                "modules": {"assembly": True, "annotation": True, "mlst": True, "amr": False},
            }
        ),
        encoding="utf-8",
    )

    validation = get_plugin("wgs_bacannot").validate_result_dir(result)

    statuses = {row["contract_id"]: row["status"] for row in validation["contracts"]}
    assert validation["valid"] is False
    assert statuses["bacannot_assembly"] == "missing_process"
    assert statuses["bacannot_amr"] == "not_selected"


def _make_successful_run(tmp_path: Path, *, resume: bool = False):
    """Run the managed runtime against a fake pinned Bacannot Nextflow run."""
    fake = tmp_path / "nextflow"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "def write_after(flag, text):\n"
        "    if flag in args:\n"
        "        path = pathlib.Path(args[args.index(flag) + 1])\n"
        "        path.parent.mkdir(parents=True, exist_ok=True)\n"
        "        path.write_text(text)\n"
        "write_after('-with-trace', "
        "'task_id\\thash\\tprocess\\ttag\\tattempt\\tstatus\\texit\\tworkdir\\n'"
        "+ '1\\taa/111\\tBACANNOT:UNICYCLER\\tS1\\t1\\tCOMPLETED\\t0\\twork/aa/111\\n'"
        "+ '2\\tbb/222\\tBACANNOT:PROKKA\\tS1\\t1\\tCOMPLETED\\t0\\twork/bb/222\\n'"
        "+ '3\\tcc/333\\tBACANNOT:MLST\\tS1\\t1\\tCACHED\\t0\\twork/cc/333\\n'"
        "+ '4\\tdd/444\\tBACANNOT:AMRFINDER\\tS1\\t1\\tCOMPLETED\\t0\\twork/dd/444\\n')\n"
        "write_after('-with-report', '<html>report</html>')\n"
        "write_after('-with-timeline', '<html>timeline</html>')\n"
        "write_after('-with-dag', '<html>dag</html>')\n"
        "write_after('-log', 'nextflow log')\n"
        "out = pathlib.Path(args[args.index('--output') + 1])\n"
        "(out / 'S1/assembly/unicycler_S1').mkdir(parents=True, exist_ok=True)\n"
        "(out / 'S1/assembly/unicycler_S1/assembly.fasta').write_text('>c1\\nACGTACGT\\n')\n"
        "(out / 'S1/annotation').mkdir(parents=True, exist_ok=True)\n"
        "(out / 'S1/annotation/S1.fna').write_text('>c1\\nACGTACGT\\n')\n"
        "(out / 'S1/annotation/S1.gff').write_text("
        "'c1\\tProkka\\tCDS\\t1\\t8\\t.\\t+\\t0\\tID=x;product=p\\n')\n"
        "(out / 'S1/MLST').mkdir(parents=True, exist_ok=True)\n"
        "(out / 'S1/MLST/S1_mlst_analysis.txt').write_text("
        "'S1.fna\\tsaureus\\t93\\t1\\t2\\t3\\t4\\t5\\t6\\t7\\n')\n"
        "(out / 'S1/resistance/AMRFinderPlus').mkdir(parents=True, exist_ok=True)\n"
        "amr = out / 'S1/resistance/AMRFinderPlus/AMRFinder_resistance-only.tsv'\n"
        "amr.write_text("
        "'Protein identifier\\tGene symbol\\tElement subtype\\tClass\\tMethod\\t'"
        "+ '% Identity to reference sequence\\t% Coverage of reference sequence\\n'"
        "+ 'p1\\tmecA\\tAMR\\tbeta-lactam\\tBLASTP\\t100\\t100\\n')\n"
        "work = pathlib.Path(args[args.index('-work-dir') + 1])\n"
        "for task_hash in ('aa/111', 'bb/222', 'cc/333', 'dd/444'):\n"
        "    task = work / task_hash\n"
        "    task.mkdir(parents=True, exist_ok=True)\n"
        "    (task / '.command.sh').write_text('#!/bin/sh\\ntrue\\n')\n"
        "    (task / '.command.out').write_text('ok\\n')\n"
        "    (task / '.command.err').write_text('')\n"
        "    (task / '.exitcode').write_text('0\\n')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    read1 = tmp_path / "S1_R1.fastq.gz"
    read2 = tmp_path / "S1_R2.fastq.gz"
    read1.write_bytes(gzip.compress(b"@r1\nACGT\n+\nFFFF\n"))
    read2.write_bytes(gzip.compress(b"@r2\nTGCA\n+\nFFFF\n"))
    sheet = tmp_path / "samples.tsv"
    sheet.write_text(
        f"sample_id\tplatform\tread1\tread2\nS1\tillumina\t{read1}\t{read2}\n",
        encoding="utf-8",
    )
    database = tmp_path / "db"
    database.mkdir()
    plugin = get_plugin("wgs_bacannot")
    overrides = {
        "outdir": str(tmp_path / "result"),
        "input": {"sample_sheet": str(sheet)},
        "resources": {"bacannot_db": str(database)},
    }
    if resume:
        overrides["workflow"] = {"resume": True}
    config = plugin.load_config(overrides=overrides)
    plan = plugin.build_plan(config)
    runtime = NextflowRuntime(
        plugin,
        options=RuntimeOptions(engine="nextflow", nextflow_bin=fake, smoke=True),
    )
    return plugin, config, plan, runtime


def test_managed_run_failure_writes_structured_diagnostics(tmp_path: Path) -> None:
    fake = tmp_path / "nextflow"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "def write_after(flag, text):\n"
        "    if flag in args:\n"
        "        path = pathlib.Path(args[args.index(flag) + 1])\n"
        "        path.parent.mkdir(parents=True, exist_ok=True)\n"
        "        path.write_text(text)\n"
        "write_after('-with-trace', "
        "'task_id\\thash\\tprocess\\ttag\\tattempt\\tstatus\\texit\\tworkdir\\n'"
        "+ '1\\taa/111\\tBACANNOT:UNICYCLER\\tS1\\t1\\tFAILED\\t1\\twork/aa/111\\n')\n"
        "write_after('-log', 'nextflow log')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    read1 = tmp_path / "S1_R1.fastq.gz"
    read2 = tmp_path / "S1_R2.fastq.gz"
    read1.write_bytes(gzip.compress(b"@r1\nACGT\n+\nFFFF\n"))
    read2.write_bytes(gzip.compress(b"@r2\nTGCA\n+\nFFFF\n"))
    sheet = tmp_path / "samples.tsv"
    sheet.write_text(
        f"sample_id\tplatform\tread1\tread2\nS1\tillumina\t{read1}\t{read2}\n",
        encoding="utf-8",
    )
    database = tmp_path / "db"
    database.mkdir()
    plugin = get_plugin("wgs_bacannot")
    config = plugin.load_config(
        overrides={
            "outdir": str(tmp_path / "result"),
            "input": {"sample_sheet": str(sheet)},
            "resources": {"bacannot_db": str(database)},
        }
    )
    plan = plugin.build_plan(config)
    runtime = NextflowRuntime(
        plugin,
        options=RuntimeOptions(engine="nextflow", nextflow_bin=fake, smoke=True),
    )

    with pytest.raises(ABIError) as excinfo:
        runtime.run(plan, config)

    message = str(excinfo.value)
    assert "EXTERNAL_TASK_FAILED" in message
    assert "BACANNOT:UNICYCLER" in message
    assert "S1" in message
    result_dir = tmp_path / "result"
    diagnostics = json.loads(
        (result_dir / "provenance" / "diagnostics.json").read_text(encoding="utf-8")
    )
    assert diagnostics["primary_error_code"] == "EXTERNAL_TASK_FAILED"
    failure = diagnostics["failed_attempts"][0]
    assert failure["process"] == "BACANNOT:UNICYCLER"
    assert failure["sample_id"] == "S1"
    assert failure["diagnostic_hints"]
    # Evidence must survive the failure for audit.
    attempts_text = (result_dir / "provenance" / "task_attempts.tsv").read_text(encoding="utf-8")
    assert "FAILED" in attempts_text
    manifest_path = result_dir / "provenance" / "evidence_manifest.json"
    assert verify_evidence_manifest(manifest_path) is not None


def test_resume_run_archives_previous_evidence_and_links_lineage(tmp_path: Path) -> None:
    _, config, plan, runtime = _make_successful_run(tmp_path)
    first = runtime.run(plan, config)
    previous_attempts = first.outputs["task_attempts"].read_text(encoding="utf-8")

    plugin = get_plugin("wgs_bacannot")
    resume_config = plugin.load_config(
        overrides={
            "outdir": config["outdir"],
            "input": {"sample_sheet": config["input"]["sample_sheet"]},
            "resources": {"bacannot_db": config["resources"]["bacannot_db"]},
            "workflow": {"resume": True},
        }
    )
    resume_plan = plugin.build_plan(resume_config)
    second = runtime.run(resume_plan, resume_config)

    result_dir = Path(config["outdir"])
    snapshot = json.loads(
        (result_dir / "provenance" / "external_plan_snapshot.json").read_text(encoding="utf-8")
    )
    assert snapshot["resumes_run_id"] == "wgs_bacannot:wgs_bacannot_run"
    assert snapshot["external_workflow_id"] == "wgs_bacannot:wgs_bacannot_run-r1"
    archive = result_dir / "provenance" / "previous_runs" / "wgs_bacannot-wgs_bacannot_run"
    assert (archive / "external_plan_snapshot.json").is_file()
    # Archived evidence is self-consistent and byte-identical to the first run.
    assert (archive / "task_attempts.tsv").read_text(encoding="utf-8") == previous_attempts
    assert verify_evidence_manifest(archive / "evidence_manifest.json")["valid"] is True
    new_attempts = second.outputs["task_attempts"].read_text(encoding="utf-8")
    assert "wgs_bacannot:wgs_bacannot_run-r1" in new_attempts
    assert previous_attempts not in new_attempts or new_attempts != previous_attempts


def test_resume_reconciliation_reports_cached_and_executed(tmp_path: Path) -> None:
    _, config, plan, runtime = _make_successful_run(tmp_path)
    runtime.run(plan, config)

    summary = json.loads(
        (Path(config["outdir"]) / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )

    reconciliation = summary["resume_reconciliation"]
    assert reconciliation["cached"] == 1
    assert reconciliation["executed"] == 3
    assert reconciliation["total"] == 4
    assert summary["resume_lineage"]["resumes_run_id"] is None


def test_unmapped_process_policy_fail_blocks_validation(tmp_path: Path) -> None:
    result = tmp_path / "result"
    provenance = result / "provenance"
    trace = tmp_path / "trace.tsv"
    trace.write_text("task_id\tstatus\n", encoding="utf-8")
    archive_evidence_files([(trace, "nextflow_trace")], provenance, collector_version="test-v1")
    write_task_attempts_tsv(
        [
            ExternalTaskAttempt(
                external_workflow_id="run-1",
                task_id="9",
                task_hash="zz/999",
                process_name="BACANNOT:BRAND_NEW_STEP",
                process_class="unmapped",
                sample_id="S1",
                attempt=1,
                status="COMPLETED",
            )
        ],
        provenance / "task_attempts.tsv",
    )
    snapshot = {
        "inputs": [{"sample_id": "S1", "role": "read1"}],
        "modules": {"assembly": True, "annotation": True, "mlst": True, "amr": False},
        "resolved_config": {"audit": {"unmapped_policy": "fail"}},
    }
    (provenance / "external_plan_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
    plugin = get_plugin("wgs_bacannot")

    validation = plugin.validate_result_dir(result)

    codes = {row["error_code"] for row in validation["errors"]}
    assert "UNMAPPED_PROCESSES" in codes
    assert validation["valid"] is False

    # Default (warn) policy records but does not block on unmapped processes.
    snapshot["resolved_config"] = {}
    (provenance / "external_plan_snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")
    warn_validation = plugin.validate_result_dir(result)
    warn_codes = {row["error_code"] for row in warn_validation["errors"]}
    assert "UNMAPPED_PROCESSES" not in warn_codes


def test_validation_fails_with_attribution_when_published_artifact_deleted(
    tmp_path: Path,
) -> None:
    plugin, config, plan, runtime = _make_successful_run(tmp_path)
    runtime.run(plan, config)

    mlst_file = Path(config["outdir"]) / "raw" / "bacannot" / "S1" / "MLST" / "S1_mlst_analysis.txt"
    mlst_file.unlink()

    validation = plugin.validate_result_dir(config["outdir"])

    assert validation["valid"] is False
    errors = [
        row
        for row in validation["errors"]
        if row["status"] == "artifact_missing" and row["contract_id"] == "bacannot_mlst"
    ]
    assert errors and errors[0]["sample_id"] == "S1"
    assert errors[0]["missing_outputs"][0]["role"] == "mlst_result"


def test_validation_fails_when_published_artifact_is_truncated(tmp_path: Path) -> None:
    plugin, config, plan, runtime = _make_successful_run(tmp_path)
    runtime.run(plan, config)

    mlst_file = Path(config["outdir"]) / "raw" / "bacannot" / "S1" / "MLST" / "S1_mlst_analysis.txt"
    mlst_file.write_bytes(b"")

    validation = plugin.validate_result_dir(config["outdir"])

    assert validation["valid"] is False
    invalid = [
        row
        for row in validation["errors"]
        if row["status"] == "artifact_invalid" and row["contract_id"] == "bacannot_mlst"
    ]
    assert invalid and "non_empty" in invalid[0]["invalid_outputs"][0]["validators_failed"]


def test_invalid_unmapped_policy_is_rejected(tmp_path: Path) -> None:
    plugin = get_plugin("wgs_bacannot")
    with pytest.raises(ValueError, match="unmapped_policy"):
        plugin.load_config(overrides={"audit": {"unmapped_policy": "ignore"}})


def test_external_verify_rejects_explicit_empty_artifacts_list(tmp_path: Path) -> None:
    """P0-1 review finding: an explicit empty "artifacts" list must not fall
    back to legacy "files" rows — the two verifiers must agree it is invalid."""
    source = tmp_path / "trace.tsv"
    source.write_text("task_id\tstatus\n1\tCOMPLETED\n", encoding="utf-8")
    manifest = tmp_path / "evidence_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "abi.evidence-manifest.v1",
                "complete": True,
                "artifacts": [],
                "files": [
                    {
                        "path": "raw/trace.tsv",
                        "sha256": "a" * 64,
                        "complete": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "trace.tsv").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = verify_evidence_manifest(manifest)

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "empty_manifest"
