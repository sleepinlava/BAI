import json

import pytest
from typer.testing import CliRunner

from abi.cli import app
from abi.plugins import get_plugin


def _fake_nextflow(path):
    path.write_text(
        """#!/usr/bin/env sh
trace=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-with-trace" ]; then
    shift
    trace="$1"
  fi
  shift || break
done
if [ -n "$trace" ]; then
  mkdir -p "$(dirname "$trace")"
  printf 'task_id\tname\tstatus\texit\tnative_id\texecutor\n' > "$trace"
  printf '1\tRNA1_QC_FASTP (RNA1_qc_fastp)\tCOMPLETED\t0\tlocal-1\tlocal\n' >> "$trace"
fi
printf 'fake nextflow %s\n' "$*"
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _assert_nextflow_smoke_artifacts(outdir):
    summary = json.loads((outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["engine"] == "nextflow"
    assert summary["smoke"] is True
    assert summary["status"] == "success"
    assert summary["dag"]["edges"]["RNA1_alignment_star"] == ["RNA1_qc_fastp"]
    assert summary["remote_scheduler_jobs"][0]["scheduler_job_id"] == "local-1"
    commands = (outdir / "provenance" / "commands.tsv").read_text(encoding="utf-8")
    assert "abi-nextflow-smoke" in commands
    assert "remote_scheduler_job_id" in commands
    assert "local-1" in commands
    assert "\tsuccess\t0\t" in commands
    resolved_inputs = (outdir / "provenance" / "resolved_inputs.tsv").read_text(encoding="utf-8")
    assert "NOT_CONFIGURED" not in resolved_inputs
    assert (outdir / "tables" / "gene_expression.tsv").exists()
    assert (outdir / "report" / "report.md").exists()
    assert (outdir / "nextflow" / "workflow.nf").exists()


def test_abi_metatranscriptomics_dry_run_writes_portability_artifacts(tmp_path):
    outdir = tmp_path / "abi_transcriptomics"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "dry-run",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--no-progress",
        ],
    )

    assert result.exit_code == 0, result.output
    commands = (outdir / "provenance" / "commands.tsv").read_text(encoding="utf-8")
    assert "fastp" in commands
    assert "STAR" in commands
    assert "featureCounts" in commands
    assert (outdir / "tables" / "gene_expression.tsv").exists()
    resolved_inputs = (outdir / "provenance" / "resolved_inputs.tsv").read_text(encoding="utf-8")
    assert "GENOME_INDEX_NOT_CONFIGURED" in resolved_inputs
    assert "ANNOTATION_GTF_NOT_CONFIGURED" in resolved_inputs
    progress_events = outdir / "provenance" / "progress.jsonl"
    progress_snapshot = outdir / "provenance" / "progress.json"
    assert progress_events.exists()
    assert progress_snapshot.exists()
    summary = json.loads((outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["progress_events"] == str(progress_events)
    assert summary["run_id"]
    assert summary["abi_version"]
    assert "git_commit" in summary
    assert "git_dirty" in summary
    assert "runtime_lock_id" in summary
    assert (outdir / "provenance" / "resource_manifest.json").exists()
    methods = (outdir / "provenance" / "methods.md").read_text(encoding="utf-8")
    assert "| genome_index | not_configured " in methods
    assert "| annotation_gtf | not_configured " in methods
    assert "GENOME_INDEX_NOT_CONFIGURED" in methods
    assert "ANNOTATION_GTF_NOT_CONFIGURED" in methods
    events = [json.loads(line) for line in progress_events.read_text(encoding="utf-8").splitlines()]
    assert [event["event"] for event in events] == ["run_started", "run_completed"]
    resources = json.loads((outdir / "provenance" / "resources.json").read_text(encoding="utf-8"))[
        "resources"
    ]
    required_resource_fields = {
        "resource_id",
        "path",
        "status",
        "version",
        "source",
        "checksum",
        "license",
        "validated_at",
    }
    assert resources
    assert all(required_resource_fields <= set(resource) for resource in resources)
    version_rows = (outdir / "provenance" / "tool_versions.tsv").read_text(encoding="utf-8")
    assert "\tnot_captured\n" in version_rows
    recorded_tool_ids = {
        line.split("\t", 1)[0] for line in version_rows.splitlines()[1:] if line.strip()
    }
    assert recorded_tool_ids == set(summary["selected_tools"])


def test_abi_inspect_reports_placeholder_inputs(tmp_path):
    outdir = tmp_path / "abi_transcriptomics"
    runner = CliRunner()
    dry_run = runner.invoke(
        app,
        [
            "dry-run",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--no-progress",
        ],
    )
    assert dry_run.exit_code == 0, dry_run.output

    result = runner.invoke(
        app,
        ["inspect", "--result-dir", str(outdir), "--output-json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"]["dry_run"] is True
    assert payload["result"]["execution_mode"] == "dry_run"
    assert payload["result"]["biological_result_ready"] is False
    assert payload["result"]["missing_or_placeholder_inputs"]
    assert "GENOME_INDEX_NOT_CONFIGURED" in result.output


@pytest.mark.parametrize(
    ("preset", "populated_tables", "expected_empty_table"),
    [
        (
            "p0_taxonomy",
            ("qc_summary", "host_removal_summary", "taxonomy_abundance"),
            "functional_abundance",
        ),
        (
            "p1_humann4",
            ("qc_summary", "host_removal_summary", "functional_abundance"),
            "taxonomy_abundance",
        ),
    ],
)
def test_easymetagenome_strict_validation_is_preset_aware(
    tmp_path, preset, populated_tables, expected_empty_table
):
    reads = []
    for mate in (1, 2):
        path = tmp_path / f"S1_R{mate}.fastq.gz"
        path.write_bytes(b"reads")
        reads.append(path)
    sample_sheet = tmp_path / "samples.tsv"
    sample_sheet.write_text(
        f"sample_id\tr1\tr2\tgroup\nS1\t{reads[0]}\t{reads[1]}\tcase\n",
        encoding="utf-8",
    )
    config = tmp_path / f"{preset}.yaml"
    config.write_text(
        f"workflow:\n  preset: {preset}\ninput:\n  sample_sheet: {sample_sheet}\n",
        encoding="utf-8",
    )
    outdir = tmp_path / "result"
    runner = CliRunner()
    dry_run = runner.invoke(
        app,
        [
            "dry-run",
            "--type",
            "easymetagenome",
            "--config",
            str(config),
            "--sample-sheet",
            str(sample_sheet),
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "logs"),
            "--no-progress",
        ],
    )
    assert dry_run.exit_code == 0, dry_run.output

    schemas = get_plugin("easymetagenome").table_schemas()
    for table_name in populated_tables:
        columns = list(schemas[table_name])
        (outdir / "tables" / f"{table_name}.tsv").write_text(
            "\t".join(columns) + "\n" + "\t".join("value" for _ in columns) + "\n",
            encoding="utf-8",
        )

    result = runner.invoke(
        app,
        [
            "validate-result",
            "--result-dir",
            str(outdir),
            "--require-nonempty-tables",
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"]["valid"] is True
    assert payload["result"]["tables"][expected_empty_table]["rows"] == 0


def test_abi_report_regenerates_transcriptomics_report(tmp_path):
    outdir = tmp_path / "abi_transcriptomics"
    runner = CliRunner()
    dry_run = runner.invoke(
        app,
        [
            "dry-run",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--no-progress",
        ],
    )
    assert dry_run.exit_code == 0, dry_run.output

    result = runner.invoke(
        app,
        ["report", "--type", "metatranscriptomics", "--result-dir", str(outdir)],
    )

    assert result.exit_code == 0, result.output
    assert (outdir / "report" / "report.md").exists()
    assert (outdir / "report" / "report.html").exists()


def test_abi_validate_result_accepts_transcriptomics_dry_run(tmp_path):
    outdir = tmp_path / "abi_transcriptomics"
    runner = CliRunner()
    dry_run = runner.invoke(
        app,
        [
            "dry-run",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--no-progress",
        ],
    )
    assert dry_run.exit_code == 0, dry_run.output

    result = runner.invoke(
        app,
        [
            "validate-result",
            "--result-dir",
            str(outdir),
            "--allow-empty-tables",
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["command"] == "abi_validate_result"
    assert payload["result"]["valid"] is True
    assert payload["result"]["analysis_type"] == "metatranscriptomics"
    assert payload["result"]["tables"]["gene_expression"]["exists"] is True
    assert payload["result"]["artifacts"]["provenance/progress.jsonl"]["exists"] is True


def test_abi_export_nextflow_writes_dsl2_script(tmp_path):
    outdir = tmp_path / "abi_transcriptomics"
    workflow = tmp_path / "workflow.nf"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "export-nextflow",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--output",
            str(workflow),
        ],
    )

    assert result.exit_code == 0, result.output
    script = workflow.read_text(encoding="utf-8")
    assert "nextflow.enable.dsl=2" in script
    assert "process RNA1_QC_FASTP" in script
    assert "workflow" in script


def test_abi_export_nextflow_smoke_writes_runnable_smoke_script(tmp_path):
    outdir = tmp_path / "abi_transcriptomics"
    workflow = tmp_path / "workflow.nf"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "export-nextflow",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--output",
            str(workflow),
            "--smoke",
        ],
    )

    assert result.exit_code == 0, result.output
    script = workflow.read_text(encoding="utf-8")
    assert "// Export mode: smoke" in script
    assert "ABI Nextflow smoke step" in script
    assert "fastp -i" not in script


def test_abi_run_engine_nextflow_smoke_writes_abi_artifacts_with_fake_nextflow(
    tmp_path,
):
    outdir = tmp_path / "abi_transcriptomics"
    nextflow = _fake_nextflow(tmp_path / "nextflow")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--engine",
            "nextflow",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--nextflow-bin",
            str(nextflow),
            "--smoke",
            "--confirm-execution",
        ],
    )

    assert result.exit_code == 0, result.output
    _assert_nextflow_smoke_artifacts(outdir)


def test_abi_run_plain_cli_requires_confirmation(tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--engine",
            "nextflow",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(tmp_path / "unconfirmed_run"),
            "--log-dir",
            str(tmp_path / "log"),
            "--smoke",
        ],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "confirmation_required"
    assert payload["command"] == "run"


def test_abi_run_nextflow_alias_uses_runtime_layer(tmp_path):
    outdir = tmp_path / "abi_transcriptomics"
    nextflow = _fake_nextflow(tmp_path / "nextflow")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run-nextflow",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--nextflow-bin",
            str(nextflow),
            "--confirm-execution",
        ],
    )

    assert result.exit_code == 0, result.output
    _assert_nextflow_smoke_artifacts(outdir)


def test_abi_metagenomic_plasmid_adapter_plan_keeps_autoplasm_route(tmp_path):
    outdir = tmp_path / "abi_plasmid"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "plan",
            "--type",
            "metagenomic_plasmid",
            "--config",
            "examples/config_minimal.yaml",
            "--profile",
            "dry_run",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
        ],
    )

    assert result.exit_code == 0, result.output
    plan = (outdir / "execution_plan.json").read_text(encoding="utf-8")
    assert '"analysis_type": "metagenomic_plasmid"' in plan
    assert "genomad" in plan


def test_abi_metagenomic_plasmid_no_progress_writes_progress_artifacts(tmp_path):
    outdir = tmp_path / "abi_plasmid"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "dry-run",
            "--type",
            "metagenomic_plasmid",
            "--config",
            "examples/config_minimal.yaml",
            "--profile",
            "dry_run",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--no-progress",
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    progress_events = outdir / "provenance" / "progress.jsonl"
    progress_snapshot = outdir / "provenance" / "progress.json"
    assert payload["result"]["outputs"]["progress_events"] == str(progress_events)
    assert progress_events.exists()
    assert progress_snapshot.exists()
    snapshot = json.loads(progress_snapshot.read_text(encoding="utf-8"))
    assert snapshot["status"] == "success"
    assert snapshot["record_progress"] is False
    plan = json.loads((outdir / "execution_plan.json").read_text(encoding="utf-8"))
    assert plan["analysis_type"] == "metagenomic_plasmid"
    # Shared-executor semantics (WP2): the version table covers the plan's
    # selected tools (plus configured extras), not the whole registry.
    # 共享执行器语义（WP2）：版本表覆盖计划选中的工具（及配置的额外项），
    # 而非整个 registry。
    version_lines = (
        (outdir / "provenance" / "tool_versions.tsv").read_text(encoding="utf-8").splitlines()
    )
    selected_tools = [str(tool) for tool in plan["selected_tools"]]
    assert selected_tools
    assert len(version_lines) >= 1 + len(selected_tools)
    listed_tools = {line.split("\t", 1)[0] for line in version_lines[1:]}
    assert set(selected_tools) <= listed_tools
    assert all(line.endswith("\tnot_captured") for line in version_lines[1:])
    resources = json.loads((outdir / "provenance" / "resources.json").read_text(encoding="utf-8"))[
        "resources"
    ]
    required_resource_fields = {
        "resource_id",
        "path",
        "status",
        "version",
        "source",
        "checksum",
        "license",
        "validated_at",
    }
    assert resources
    assert all(required_resource_fields <= set(resource) for resource in resources)

    validation = runner.invoke(
        app,
        [
            "validate-result",
            "--result-dir",
            str(outdir),
            "--allow-empty-tables",
            "--output-json",
        ],
    )

    assert validation.exit_code == 0, validation.output
    validation_payload = json.loads(validation.output)
    assert validation_payload["result"]["valid"] is True
    assert validation_payload["result"]["analysis_type"] == "metagenomic_plasmid"


def test_abi_cli_output_json_wraps_plan_result(tmp_path):
    outdir = tmp_path / "abi_transcriptomics_json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "plan",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["command"] == "plan"
    assert payload["result"]["analysis_type"] == "metatranscriptomics"
    assert payload["result"]["plan_path"] == str(outdir / "execution_plan.json")


def test_abi_cli_output_json_run_requires_confirmation(tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(tmp_path / "run_requires_confirmation"),
            "--log-dir",
            str(tmp_path / "log"),
            "--smoke",
            "--output-json",
        ],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "confirmation_required"
    assert payload["command"] == "run"


def test_abi_cli_output_json_run_executes_after_confirmation(tmp_path):
    outdir = tmp_path / "abi_transcriptomics_json_run"
    nextflow = _fake_nextflow(tmp_path / "nextflow")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--engine",
            "nextflow",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "log"),
            "--nextflow-bin",
            str(nextflow),
            "--smoke",
            "--confirm-execution",
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["command"] == "run"
    assert payload["result"]["engine"] == "nextflow"
    _assert_nextflow_smoke_artifacts(outdir)


def test_abi_export_agent_context_outputs_machine_readable_guidance():
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["export-agent-context", "--type", "metatranscriptomics", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["command"] == "export_agent_context"
    context = payload["result"]
    assert context["analysis_type"] == "metatranscriptomics"
    assert context["safe_sequence"] == [
        "list_types",
        "query",
        "plan",
        "check",
        "dry_run",
        "inspect",
        "run",
        "inspect",
        "abi_validate_result",
        "report",
    ]
    assert context["execution_requires_confirmation"] is True
    assert "abi_run" in context["unsafe_tools"]
    assert "abi_run" not in context["default_exported_tools"]
    assert "gene_expression" in context["standard_tables"]


def test_abi_doctor_agent_outputs_short_operating_guide():
    runner = CliRunner()

    result = runner.invoke(app, ["doctor-agent", "--type", "metatranscriptomics"])

    assert result.exit_code == 0, result.output
    assert "ABI agent guide for metatranscriptomics" in result.output
    assert "Safe call order" in result.output
    assert "gene_expression" in result.output


def test_abi_doctor_agent_output_json_uses_agent_envelope():
    runner = CliRunner()

    result = runner.invoke(app, ["doctor-agent", "--type", "metatranscriptomics", "--output-json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["command"] == "doctor_agent"


def test_abi_check_resources_reports_generic_plugin_placeholders():
    runner = CliRunner()

    result = runner.invoke(app, ["check-resources", "--type", "metatranscriptomics"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["command"] == "check_resources"
    rows = payload["result"]["resources"]
    by_id = {row["resource_id"]: row for row in rows}
    assert by_id["genome_index"]["status"] == "not_configured"
    assert by_id["annotation_gtf"]["status"] == "not_configured"


def test_abi_setup_resources_dry_run_uses_metagenomic_resource_manager():
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "setup-resources",
            "--type",
            "metagenomic_plasmid",
            "--config",
            "examples/config_minimal.yaml",
            "--profile",
            "dry_run",
            "--resource",
            "genomad",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows[0]["resource_id"] == "genomad"
    assert rows[0]["status"] == "planned"
    assert rows[0]["command"][0] == "genomad"


def test_abi_query_always_uses_agent_envelope():
    result = CliRunner().invoke(
        app,
        ["query", "--type", "rnaseq_expression", "--what", "platforms"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["command"] == "query"
    assert payload["result"]["platforms"] == ["illumina"]


def test_viral_viwrap_compat_workflow_is_discoverable_through_unified_query():
    result = CliRunner().invoke(
        app,
        ["query", "--type", "viral_viwrap", "--what", "workflows"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [item["id"] for item in payload["result"]["workflows"]] == ["viwrap_compat"]


@pytest.mark.parametrize(
    "analysis_type",
    [
        "amplicon_16s",
        "easymetagenome",
        "metagenomic_plasmid",
        "metatranscriptomics",
        "rnaseq_expression",
        "viral_viwrap",
        "wgs_bacteria",
    ],
)
def test_abi_init_creates_workspace_for_every_plugin(tmp_path, analysis_type):
    workspace = tmp_path / analysis_type

    result = CliRunner().invoke(
        app,
        ["init", "--type", analysis_type, "--outdir", str(workspace)],
    )

    assert result.exit_code == 0, result.output
    assert (workspace / "config" / f"{analysis_type}.yaml").is_file()
    sample_sheet = workspace / "samples.tsv"
    assert sample_sheet.is_file()
    assert sample_sheet.read_text(encoding="utf-8").startswith("sample_id\t")


def test_abi_local_smoke_skips_external_tools_and_writes_provenance(tmp_path):
    outdir = tmp_path / "local_smoke"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--type",
            "metatranscriptomics",
            "--outdir",
            str(outdir),
            "--log-dir",
            str(tmp_path / "logs"),
            "--smoke",
            "--confirm-execution",
            "--output-json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    summary = json.loads((outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    commands = (outdir / "provenance" / "commands.tsv").read_text(encoding="utf-8")
    assert "mock tool execution skipped" in commands


def test_run_nextflow_alias_matches_run_engine_nextflow(tmp_path):
    """P1-2: the alias and the canonical command must stay behaviorally identical.

    Same fake nextflow, same arguments; both code paths must produce the same
    run summary and artifact inventory (modulo the run directory itself).
    """
    runner = CliRunner()
    nextflow = _fake_nextflow(tmp_path / "nextflow")
    summaries = {}
    inventories = {}
    for name, argv in (
        (
            "run",
            [
                "run",
                "--engine",
                "nextflow",
            ],
        ),
        (
            "alias",
            [
                "run-nextflow",
            ],
        ),
    ):
        outdir = tmp_path / name / "abi_transcriptomics"
        result = runner.invoke(
            app,
            [
                *argv,
                "--type",
                "metatranscriptomics",
                "--outdir",
                str(outdir),
                "--log-dir",
                str(tmp_path / name / "log"),
                "--nextflow-bin",
                str(nextflow),
                "--smoke",
                "--confirm-execution",
            ],
        )
        assert result.exit_code == 0, result.output
        _assert_nextflow_smoke_artifacts(outdir)
        summaries[name] = json.loads(
            (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
        )
        inventories[name] = sorted(
            str(p.relative_to(outdir)) for p in outdir.rglob("*") if p.is_file()
        )

    # run-summary is identical except run-identity fields that necessarily
    # differ per run (run id, timestamps, and every artifact path embedding
    # the run directory; plan_id binds the outdir, so the two run roots also
    # produce different digests by design). Normalize both runs' roots and
    # per-run identity fields to placeholders, then compare the summaries.
    # run-summary 除每次运行必然不同的身份字段外完全一致（run id、时间戳、
    # 以及每个嵌入运行目录的产物路径；plan_id 绑定 outdir，两个运行根按设
    # 计产生不同摘要）。归一化运行根与身份字段后比较完整摘要。
    per_run_keys = ("run_id", "plan_id", "resumes_run_id", "previous_run_archive")

    def normalize(obj: object, root: str) -> object:
        if isinstance(obj, dict):
            return {
                k: ("<per_run>" if k in per_run_keys else normalize(v, root))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [normalize(v, root) for v in obj]
        if isinstance(obj, str):
            return obj.replace(root, "<run_root>")
        return obj

    assert normalize(summaries["run"], str(tmp_path / "run")) == normalize(
        summaries["alias"], str(tmp_path / "alias")
    )
    assert inventories["run"] == inventories["alias"]
