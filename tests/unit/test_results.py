from __future__ import annotations

from abi.plugins import get_plugin
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
