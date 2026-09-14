from __future__ import annotations

from abi.plugin_registry import get_plugin
from abi.results import (
    ABIResultWriter,
    completed_abi_result_outputs,
    validate_abi_result_dir,
)
from abi.schemas import ExecutionPlan, SampleContext, SampleInput
from abi.tools import ToolRegistry


def test_result_writer_produces_a_self_validating_bundle(tmp_path):
    plugin = get_plugin("metatranscriptomics")
    sample = SampleInput(sample_id="S1", platform="illumina")
    context = SampleContext(samples=[sample], multi_sample=False, has_groups=False)
    plan = ExecutionPlan(
        project_name="result-writer",
        analysis_type=plugin.plugin_id,
        mode="auto",
        threads=1,
        outdir=str(tmp_path),
        log_dir=str(tmp_path / "logs"),
        samples=[sample],
        steps=[],
        selected_tools=[],
        sample_context=context,
    )
    writer = ABIResultWriter(plugin, ToolRegistry([]))

    outputs = writer.write(
        plan=plan,
        config={"outdir": str(tmp_path)},
        command_rows=[],
        status="success",
        smoke=True,
        trace_rows=[{"task_id": "1", "status": "COMPLETED"}],
    )
    validation = validate_abi_result_dir(tmp_path)
    completed = completed_abi_result_outputs(tmp_path)

    assert outputs["progress_events"].exists()
    assert outputs["trace"].exists()
    assert validation["valid"] is True
    assert validation["analysis_type"] == "metatranscriptomics"
    assert completed is not None
    assert completed["plan"] == outputs["plan"]
    assert completed["report"] == outputs["report"]
    assert completed["trace"] == outputs["trace"]


def test_result_validation_reports_missing_and_malformed_artifacts(tmp_path):
    missing = validate_abi_result_dir(tmp_path / "missing")
    assert missing["status"] == "missing"

    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "execution_plan.json").write_text("{bad", encoding="utf-8")
    malformed = validate_abi_result_dir(tmp_path)
    assert malformed["valid"] is False
    assert completed_abi_result_outputs(tmp_path) is None
    assert any("Invalid JSON" in error for error in malformed["errors"])


def test_result_writer_emits_canonical_progress_event_schema(tmp_path):
    """P1-4b: writer progress.jsonl matches the provenance event schema.

    The local executor's minimal mode and ABIResultWriter (nextflow,
    snakemake, managed external runs) must produce the same timestamped,
    payload-nested two-event stream so audit replay sees one schema.
    """
    import json as jsonlib

    plugin = get_plugin("metatranscriptomics")
    sample = SampleInput(sample_id="S1", platform="illumina")
    context = SampleContext(samples=[sample], multi_sample=False, has_groups=False)
    plan = ExecutionPlan(
        project_name="progress-schema",
        analysis_type=plugin.plugin_id,
        mode="auto",
        threads=1,
        outdir=str(tmp_path),
        log_dir=str(tmp_path / "logs"),
        samples=[sample],
        steps=[],
        selected_tools=[],
        sample_context=context,
    )
    writer = ABIResultWriter(plugin, ToolRegistry([]))

    writer.write(
        plan=plan,
        config={"outdir": str(tmp_path)},
        command_rows=[],
        status="success",
        smoke=True,
    )

    events = [
        jsonlib.loads(line)
        for line in (tmp_path / "provenance" / "progress.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["event"] for event in events] == ["run_started", "run_completed"]
    for event in events:
        assert set(event) == {"timestamp", "event", "payload"}, event
        assert event["timestamp"]
        assert isinstance(event["payload"], dict)
    assert events[1]["payload"]["status"] == "success"
    # The snapshot advertised in RESULT_OUTPUT_PATHS is now written too.
    assert (tmp_path / "provenance" / "progress.json").exists()


def test_result_writer_shares_run_identity_and_history_semantics(tmp_path):
    """B2: nextflow/snakemake/hpc evidence carries the same identity fields as
    the local executor and never overwrites prior run history."""
    import json as jsonlib

    plugin = get_plugin("metatranscriptomics")
    sample = SampleInput(sample_id="S1", platform="illumina")
    context = SampleContext(samples=[sample], multi_sample=False, has_groups=False)

    def _plan() -> ExecutionPlan:
        return ExecutionPlan(
            project_name="backend-identity",
            analysis_type=plugin.plugin_id,
            mode="auto",
            threads=1,
            outdir=str(tmp_path),
            log_dir=str(tmp_path / "logs"),
            samples=[sample],
            steps=[],
            selected_tools=[],
            sample_context=context,
        )

    writer = ABIResultWriter(plugin, ToolRegistry([]))
    writer.write(
        plan=_plan(),
        config={"outdir": str(tmp_path)},
        command_rows=[],
        status="success",
        smoke=True,
        plan_id="sha256:" + "a" * 64,
    )
    first = jsonlib.loads((tmp_path / "provenance" / "run_summary.json").read_text())
    assert first["run_id"]
    assert first["abi_version"]
    assert first["plan_id"] == "sha256:" + "a" * 64
    assert first["resumes_run_id"] is None
    assert first["previous_run_archive"] is None
    first_commands = (tmp_path / "provenance" / "commands.tsv").read_text()

    # A resumed rewrite archives the prior evidence and links to it; a resume
    # records resumes_run_id while the fresh run_id stays independent.
    # 恢复式重写先归档先前证据并链接它；恢复记录 resumes_run_id，新 run_id 保持独立。
    writer.write(
        plan=_plan(),
        config={"outdir": str(tmp_path)},
        command_rows=[],
        status="success",
        smoke=True,
        resume=True,
    )
    second = jsonlib.loads((tmp_path / "provenance" / "run_summary.json").read_text())
    assert second["run_id"] != first["run_id"]
    assert second["resumes_run_id"] == first["run_id"]
    archive = tmp_path / "provenance" / second["previous_run_archive"]
    assert jsonlib.loads((archive / "run_summary.json").read_text())["run_id"] == first["run_id"]
    assert (archive / "commands.tsv").read_text() == first_commands
