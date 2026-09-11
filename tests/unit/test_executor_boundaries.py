from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from abi.contracts.step_contract import ContractViolationError, compute_file_checksum
from abi.errors import InputPolicyError
from abi.executor import (
    GenericABIExecutor,
    _build_assertion_context,
    _cleanup_failed_step_output_dir,
    _execution_options,
    _filename_has_read_pair,
    _output_candidate_score,
    _propagate_resolved_paths,
    _read_pair_for_key,
    _resolve_actual_outputs,
    _symlink_resolved_outputs,
    _tool_failure_reason,
)
from abi.internal import FunctionInternalHandler, InternalHandlerResult
from abi.provenance import RunLogger
from abi.schemas import ExecutionPlan, PlanStep, SampleContext, SampleInput, ToolError
from abi.tables import StandardTableManager
from abi.tools import ToolRegistry


class _Logger:
    def __init__(self, path: Path) -> None:
        self.log_file = path
        self.rows = []

    def log_step(self, step, **kwargs) -> None:
        self.rows.append((step.step_id, kwargs))


class _Tables:
    def __init__(self) -> None:
        self.rows = []

    def ensure_tables(self, path):
        return None

    def summarize(self, path):
        return {}

    def append_rows(self, path, rows):
        self.rows.append(rows)
        return list(rows)


class _Registry:
    def __init__(self, skill=None, *, registered: bool = True) -> None:
        self.skill = skill
        self.registered = registered

    def has(self, tool_id: str) -> bool:
        return self.registered and tool_id == "tool"

    def get(self, tool_id: str, *, mock_tools: bool = False):
        """Registry metadata lookup used by output-directory policies."""
        return {}

    def list_tools(self):
        return [{"id": "tool", "executable": "tool"}]

    def check_tools(self, *, mock_tools: bool = False, config=None):
        return []

    def create(self, tool_id: str, *, mock_tools: bool = False):
        return self.skill


class _Skill:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result or SimpleNamespace(return_code=0, status="success", outputs={})
        self.error = error
        self.params = None

    def build_command(self, params):
        return ["tool", "--output", str(params.get("output_dir", ""))]

    def run(self, params, *, dry_run: bool):
        self.params = params
        if self.error:
            raise self.error
        return self.result


def _step(**overrides) -> PlanStep:
    values = {
        "step_id": "step",
        "step_name": "Step",
        "tool_id": "tool",
        "category": "test",
        "sample_id": "S1",
    }
    values.update(overrides)
    return PlanStep(**values)


def _executor(
    tmp_path: Path,
    *,
    skill=None,
    registered: bool = True,
    handlers=None,
    enforce_contracts: bool = True,
) -> GenericABIExecutor:
    executor = GenericABIExecutor(
        _Registry(skill, registered=registered),
        _Logger(tmp_path / "run.log"),
        table_manager=_Tables(),
        parse_outputs=lambda tool_id, output_dir, sample_id: {
            "summary": [{"sample_id": sample_id}]
        },
        internal_handlers=handlers,
        enforce_contracts=enforce_contracts,
    )
    executor._config = {"outdir": str(tmp_path)}
    return executor


def test_cleanup_failed_step_output_dir_is_opt_in_and_scoped(tmp_path: Path) -> None:
    output_dir = tmp_path / "out" / "02_host_removal" / "S1"
    output_dir.mkdir(parents=True)
    partial = output_dir / "_temp.sam"
    partial.write_bytes(b"partial")
    step = _step(
        params={"_cleanup_failed_output_dir": "true"},
        outputs={"output_dir": str(output_dir)},
    )

    _cleanup_failed_step_output_dir(step, tmp_path / "out")

    assert output_dir.is_dir()
    assert not partial.exists()


def test_prepare_output_directories_rejects_all_outputs_outside_root(tmp_path: Path) -> None:
    outdir = tmp_path / "pipeline"
    outside_file = tmp_path / "escaped" / "result.tsv"
    step = _step(
        outputs={
            "output_dir": str(outdir / "safe"),
            "result": str(outside_file),
        }
    )

    with pytest.raises(InputPolicyError, match="result for step step escapes output root"):
        GenericABIExecutor._ensure_step_output_dirs([step], outdir=outdir)

    assert not outside_file.parent.exists()


def test_resume_reuses_only_validated_nonempty_file_outputs(tmp_path: Path) -> None:
    output = tmp_path / "result.tsv"
    output.write_text("value\n1\n", encoding="utf-8")
    skill = _Skill()
    executor = _executor(tmp_path, skill=skill)
    step = _step(
        outputs={"result": str(output)},
        params={"_contract": {"outputs": {"result": {"type": "file"}}}},
    )

    row, error = executor._execute_step(
        step,
        dry_run=False,
        resume=True,
        provenance=tmp_path / "provenance",
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )

    assert error is None
    assert row["status"] == "resumed"
    assert skill.params is None


def test_resume_reruns_step_when_declared_output_is_missing(tmp_path: Path) -> None:
    output = tmp_path / "missing.tsv"
    skill = _Skill()
    executor = _executor(tmp_path, skill=skill)
    step = _step(
        outputs={"result": str(output), "output_dir": str(tmp_path)},
        params={"_contract": {"outputs": {"result": {"type": "file"}}}},
    )

    row, error = executor._execute_step(
        step,
        dry_run=False,
        resume=True,
        provenance=tmp_path / "provenance",
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )

    assert error is None
    assert row["status"] == "success"
    assert skill.params is not None


def test_prepare_output_directories_rejects_symlink_escape_before_mkdir(tmp_path: Path) -> None:
    outdir = tmp_path / "pipeline"
    outside = tmp_path / "outside"
    outdir.mkdir()
    outside.mkdir()
    (outdir / "escape").symlink_to(outside, target_is_directory=True)
    step = _step(outputs={"output_dir": str(outdir / "escape" / "created")})

    with pytest.raises(InputPolicyError, match="output_dir for step step escapes output root"):
        GenericABIExecutor._ensure_step_output_dirs([step], outdir=outdir)

    assert not (outside / "created").exists()


def test_managed_output_roots_do_not_allow_unrelated_external_paths(tmp_path: Path) -> None:
    outdir = tmp_path / "pipeline"
    managed = tmp_path / "managed"
    escaped = tmp_path / "escaped" / "result.tsv"
    step = _step(outputs={"result": str(escaped)})

    with pytest.raises(InputPolicyError, match="result for step step escapes output root"):
        GenericABIExecutor._ensure_step_output_dirs(
            [step],
            outdir=outdir,
            managed_output_roots=[managed],
        )

    assert not escaped.parent.exists()


def test_managed_output_roots_reject_symlink_escape(tmp_path: Path) -> None:
    outdir = tmp_path / "pipeline"
    managed = tmp_path / "managed"
    outside = tmp_path / "outside"
    managed.mkdir()
    outside.mkdir()
    (managed / "escape").symlink_to(outside, target_is_directory=True)
    step = _step(outputs={"output_dir": str(managed / "escape" / "created")})

    with pytest.raises(InputPolicyError, match="output_dir for step step escapes output root"):
        GenericABIExecutor._ensure_step_output_dirs(
            [step],
            outdir=outdir,
            managed_output_roots=[managed],
        )

    assert not (outside / "created").exists()


def test_prepare_output_directories_preserves_must_not_exist(tmp_path: Path) -> None:
    outdir = tmp_path / "pipeline"
    output_dir = outdir / "parent" / "tool-created"
    step = _step(
        outputs={
            "output_dir": str(output_dir),
            "result": str(output_dir / "result.tsv"),
        }
    )
    registry = SimpleNamespace(
        has=lambda tool_id: True,
        get=lambda tool_id: {"output_dir_policy": "must_not_exist"},
    )

    GenericABIExecutor._ensure_step_output_dirs([step], registry=registry, outdir=outdir)

    assert output_dir.parent.is_dir()
    assert not output_dir.exists()


def test_generic_executor_parallel_dry_run_preserves_plan_order(tmp_path: Path) -> None:
    samples = [
        SampleInput(sample_id="S1", platform="assembly", assembly="S1.fa"),
        SampleInput(sample_id="S2", platform="assembly", assembly="S2.fa"),
    ]
    context = SampleContext(samples, True, False, True, False)
    steps = [
        _step(step_id="S1_step", sample_id="S1"),
        _step(step_id="S2_step", sample_id="S2"),
        _step(step_id="project_step", sample_id=None),
    ]
    plan = ExecutionPlan(
        project_name="parallel",
        mode="auto",
        threads=1,
        outdir=str(tmp_path / "out"),
        log_dir=str(tmp_path / "logs"),
        samples=samples,
        sample_context=context,
        selected_tools=[],
        steps=steps,
    )
    executor = GenericABIExecutor(
        ToolRegistry([]),
        RunLogger(tmp_path / "logs"),
        table_manager=StandardTableManager({"summary": ["sample_id"]}),
        parse_outputs=lambda *args: {},
    )

    outputs = executor.run(
        plan,
        {
            "outdir": str(tmp_path / "out"),
            "execution": {
                "parallel": True,
                "workers": 2,
                "progress": False,
                "error_policy": "continue",
            },
        },
        dry_run=True,
    )

    command_lines = outputs["commands"].read_text(encoding="utf-8").splitlines()
    assert [line.split("\t", 1)[0] for line in command_lines[1:]] == [
        "S1_step",
        "S2_step",
        "project_step",
    ]


def test_generic_executor_waits_for_batch_cleanup_before_starting_next_samples(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    def record_step(step, config, context):
        del config, context
        events.append(f"start:{step.step_id}")
        time.sleep(float(step.params.get("delay", 0)))
        events.append(f"done:{step.step_id}")
        return InternalHandlerResult(message="recorded")

    samples = [
        SampleInput(sample_id=sample_id, platform="assembly", assembly=f"{sample_id}.fa")
        for sample_id in ("S1", "S2", "S3")
    ]
    context = SampleContext(samples, True, False, True, False)
    steps = []
    for sample in samples:
        handler = {"_internal_handler": {"handler_id": "test.record", "execution_scope": "worker"}}
        steps.extend(
            [
                _step(
                    step_id=f"{sample.sample_id}_work",
                    sample_id=sample.sample_id,
                    tool_id="internal",
                    params={**handler, "delay": 0.2 if sample.sample_id == "S2" else 0},
                ),
                _step(
                    step_id=f"{sample.sample_id}_cleanup",
                    sample_id=sample.sample_id,
                    tool_id="internal",
                    params={**handler},
                    batch_cleanup=True,
                ),
            ]
        )
    plan = ExecutionPlan(
        project_name="batched",
        mode="auto",
        threads=1,
        outdir=str(tmp_path / "out"),
        log_dir=str(tmp_path / "logs"),
        samples=samples,
        sample_context=context,
        selected_tools=[],
        steps=steps,
    )
    executor = GenericABIExecutor(
        ToolRegistry([]),
        RunLogger(tmp_path / "logs"),
        table_manager=StandardTableManager({"summary": ["sample_id"]}),
        parse_outputs=lambda *args: {},
        internal_handlers={
            "test.record": FunctionInternalHandler("test.record", record_step),
        },
    )

    outputs = executor.run(
        plan,
        {
            "outdir": str(tmp_path / "out"),
            "execution": {
                "parallel": True,
                "workers": 2,
                "batch_size": 2,
                "progress": False,
            },
        },
    )

    assert events.index("done:S2_work") < events.index("start:S1_cleanup")
    assert events.index("done:S2_cleanup") < events.index("start:S3_work")
    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    assert summary["batch_size"] == 2


def test_parallel_executor_runs_driver_validation_before_sample_chains(tmp_path: Path) -> None:
    events: list[str] = []

    def record_step(step, config, context):
        del config, context
        events.append(step.step_id)
        return InternalHandlerResult(message="recorded")

    samples = [
        SampleInput(sample_id=sample_id, platform="assembly", assembly=f"{sample_id}.fa")
        for sample_id in ("S1", "S2")
    ]
    context = SampleContext(samples, True, False, True, False)
    handler = {"handler_id": "test.record", "execution_scope": "worker"}
    steps = [
        _step(
            step_id="validate",
            sample_id=None,
            tool_id="internal",
            params={
                "_internal_handler": {
                    "handler_id": "test.record",
                    "execution_scope": "driver",
                }
            },
        ),
        *[
            _step(
                step_id=f"{sample.sample_id}_work",
                sample_id=sample.sample_id,
                tool_id="internal",
                params={"_internal_handler": handler},
            )
            for sample in samples
        ],
    ]
    plan = ExecutionPlan(
        project_name="driver-first",
        mode="auto",
        threads=1,
        outdir=str(tmp_path / "out"),
        log_dir=str(tmp_path / "logs"),
        samples=samples,
        sample_context=context,
        selected_tools=[],
        steps=steps,
    )
    executor = GenericABIExecutor(
        ToolRegistry([]),
        RunLogger(tmp_path / "logs"),
        table_manager=StandardTableManager({"summary": ["sample_id"]}),
        parse_outputs=lambda *args: {},
        internal_handlers={
            "test.record": FunctionInternalHandler("test.record", record_step),
        },
    )

    executor.run(
        plan,
        {
            "outdir": str(tmp_path / "out"),
            "execution": {"parallel": True, "workers": 2, "batch_size": 1},
        },
    )

    assert events[0] == "validate"


def test_execute_step_handles_skipped_dry_run_missing_and_external_failures(
    tmp_path: Path,
) -> None:
    executor = _executor(tmp_path, registered=False)
    skipped, error = executor._execute_step(
        _step(skipped=True, reason="not applicable"),
        dry_run=False,
        provenance=tmp_path,
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )
    dry, dry_error = executor._execute_step(
        _step(),
        dry_run=True,
        provenance=tmp_path,
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )
    missing, missing_error = executor._execute_step(
        _step(),
        dry_run=False,
        provenance=tmp_path,
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )

    assert (skipped["status"], error) == ("skipped", None)
    assert (dry["status"], dry_error) == ("dry_run", None)
    assert missing["status"] == "failed"
    assert isinstance(missing_error, ToolError)

    nonzero = SimpleNamespace(
        return_code=7,
        status="failed",
        outputs={"stderr_path": "tool.err", "stdout_path": "tool.out"},
    )
    failed_executor = _executor(tmp_path, skill=_Skill(nonzero))
    row, failed_error = failed_executor._execute_step(
        _step(outputs={"output_dir": str(tmp_path / "output")}),
        dry_run=False,
        provenance=tmp_path,
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )
    assert row["return_code"] == 7
    assert "stderr_path=tool.err" in row["reason"]
    assert isinstance(failed_error, ToolError)


def test_external_step_records_tool_exception_and_successful_parsing(tmp_path: Path) -> None:
    raised = _executor(tmp_path, skill=_Skill(error=ToolError("binary missing")))
    failed = raised._run_external_step(
        _step(outputs={"output_dir": str(tmp_path / "failed")}),
        tmp_path,
        tmp_path / "tables",
    )
    assert failed["status"] == "failed"
    assert "binary missing" in failed["reason"]
    assert (tmp_path / "step_logs" / "step.stderr.log").is_file()

    successful = _executor(tmp_path, skill=_Skill(), enforce_contracts=False)
    result = successful._run_external_step(
        _step(outputs={"output_dir": str(tmp_path / "success")}),
        tmp_path,
        tmp_path / "tables",
    )
    assert result["status"] == "success"
    assert result["parsed_status"] == "parsed"
    assert result["standard_tables"] == "summary"


def test_internal_handler_success_failure_missing_and_contract_violation(tmp_path: Path) -> None:
    success_handler = FunctionInternalHandler(
        "normalize",
        lambda *args: InternalHandlerResult(
            message="normalized", tables={"summary": [{"value": 1}]}
        ),
    )
    failed_handler = FunctionInternalHandler(
        "failed",
        lambda *args: InternalHandlerResult(status="failed", message="bad rows"),
    )
    executor = _executor(
        tmp_path,
        handlers={"normalize": success_handler, "failed": failed_handler},
    )
    assert (
        executor._run_internal_step(_step(tool_id="internal"), tmp_path, tmp_path / "tables")[
            "parsed_status"
        ]
        == "not_applicable"
    )

    with pytest.raises(ToolError, match="not registered"):
        executor._run_internal_step(
            _step(
                tool_id="internal",
                params={"_internal_handler": {"handler_id": "missing"}},
            ),
            tmp_path,
            tmp_path / "tables",
        )

    failed = executor._run_internal_step(
        _step(
            tool_id="internal",
            params={"_internal_handler": {"handler_id": "failed"}},
        ),
        tmp_path,
        tmp_path / "tables",
    )
    assert (failed["status"], failed["return_code"]) == ("failed", 1)

    success = executor._run_internal_step(
        _step(
            tool_id="internal",
            params={"_internal_handler": {"handler_id": "normalize"}},
        ),
        tmp_path,
        tmp_path / "tables",
    )
    assert success["standard_tables"] == "summary"

    contract_step = _step(
        tool_id="internal",
        outputs={"result": str(tmp_path / "missing.tsv")},
        params={
            "_internal_handler": {"handler_id": "normalize"},
            "_contract": {"outputs": {"result": {"contract": {"min_size": "1 B"}}}},
        },
    )
    with pytest.raises(ContractViolationError):
        executor._run_internal_step(contract_step, tmp_path, tmp_path / "tables")


def test_command_building_params_progress_and_internal_exception(tmp_path: Path) -> None:
    progress = SimpleNamespace(
        started=[],
        completed=[],
        step_started=lambda step: progress.started.append(step.step_id),
        step_completed=lambda step, **kwargs: progress.completed.append(kwargs),
    )
    executor = _executor(tmp_path, registered=False)
    internal = _step(
        tool_id="internal",
        params={"_internal_handler": {"handler_id": "normalize", "execution_scope": "driver"}},
    )
    assert executor._command_for_step(internal, dry_run=False)[:3] == [
        "abi",
        "internal",
        "normalize",
    ]
    assert executor._command_for_step(_step(), dry_run=False)[:2] == ["abi", "missing-wrapper"]

    executor._run_internal_step = lambda *args: (_ for _ in ()).throw(RuntimeError("broken"))
    row, error = executor._execute_step(
        internal,
        dry_run=False,
        provenance=tmp_path,
        tables_dir=tmp_path / "tables",
        progress_recorder=progress,
    )
    assert row["status"] == "failed"
    assert isinstance(error.__cause__, RuntimeError)
    assert progress.started == ["step"]
    assert progress.completed[0]["status"] == "failed"

    executor._tool_timeout_seconds = None
    params = executor._params_for_step(
        _step(inputs={"outdir": "input"}, params={"outdir": "params"}, outputs={}),
        dry_run=True,
    )
    assert params["output_dir"] == "params"
    assert params["dry_run"] is True


def test_execution_and_output_helpers_cover_corrupt_and_unresolved_paths(tmp_path: Path) -> None:
    assert _execution_options({"execution": []})["workers"] == 1
    options = _execution_options(
        {"execution": {"progress": False, "dashboard": {"enable": True}, "workers": 0}}
    )
    assert options["record_progress"] is True
    assert options["workers"] == 1

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not json", encoding="utf-8")
    context = _build_assertion_context(
        SimpleNamespace(outputs={}),
        {"_contract": {}, "number": 3, "corrupt": str(corrupt)},
    )
    assert context["output_json"] == {}
    assert _resolve_actual_outputs({"result": "abstract"}, {}, "S1") == {"result": "abstract"}
    missing_dir = tmp_path / "missing"
    assert (
        _resolve_actual_outputs({"output_dir": str(missing_dir), "result": "abstract"}, {}, "S1")[
            "result"
        ]
        == "abstract"
    )

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    custom = output_dir / "S1-result.custom"
    custom.write_text("value", encoding="utf-8")
    resolved = _resolve_actual_outputs(
        {"output_dir": str(output_dir), "result": "abstract"},
        {"output_dir": {}, "ignored": "invalid", "result": {"format": "custom"}},
        "S1",
    )
    assert resolved["result"] == str(custom)


def test_propagation_does_not_replace_a_planned_future_input_without_resolution(
    tmp_path: Path,
) -> None:
    phylogeny_dir = tmp_path / "05b_phylogeny"
    phylogeny_dir.mkdir()
    combined = phylogeny_dir / "combined.fasta"
    combined.write_text(">ASV1\nACGT\n", encoding="utf-8")
    aligned = phylogeny_dir / "aligned.fasta"

    completed = _step(outputs={"combined_fasta": str(combined)})
    downstream = _step(inputs={"aligned_fasta": str(aligned)})

    # combined.fasta is the planned output, not an output-path correction.
    # It must not overwrite FastTree's future aligned_fasta input merely
    # because the two paths share a directory and suffix.
    _propagate_resolved_paths(completed, [downstream], replacements={})

    assert downstream.inputs["aligned_fasta"] == str(aligned)


def test_structured_tool_failure_reason_includes_diagnostic_paths() -> None:
    reason = _tool_failure_reason(
        _step(),
        return_code="",
        stderr_path="step.err",
        stdout_path="step.out",
        message="binary missing",
    )
    assert "exit_code=not_started" in reason
    assert "stderr_path=step.err" in reason
    assert "stdout_path=step.out" in reason
    assert "message=binary missing" in reason


def test_propagation_helpers_and_read_pair_scoring(tmp_path: Path) -> None:
    """P2-1: the legacy genomad consensus bridge is gone from the core executor.

    The declarative pipeline resolves the single-detector case via the
    consensus internal handler plus ``fallback_depends`` — the executor must
    stay free of plugin-specific path bridges.
    """
    actual = tmp_path / "stage" / "actual" / "S1_result.tsv"
    actual.parent.mkdir(parents=True)
    actual.write_text("value", encoding="utf-8")
    planned = tmp_path / "stage" / "planned" / "result.tsv"
    _symlink_resolved_outputs(
        {"result": str(planned)},
        {"result": str(actual)},
        {"result": {"format": "tsv"}},
    )
    assert planned.is_symlink()

    downstream = _step(
        inputs={"table": str(tmp_path / "stage" / "old" / "expected.tsv")},
        params={"table": str(tmp_path / "stage" / "old" / "expected.tsv")},
    )
    _propagate_resolved_paths(SimpleNamespace(outputs={"result": str(actual)}), [downstream])
    assert downstream.inputs["table"] == str(actual)
    assert downstream.params["table"] == str(actual)

    assert _read_pair_for_key("clean_read1") == "1"
    assert _read_pair_for_key("clean_r2") == "2"
    assert _read_pair_for_key("summary") == ""
    assert _filename_has_read_pair("sample_R1.fastq.gz", "1")
    assert _output_candidate_score("clean_read1", "S1", Path("S1_R1.clean.fastq.gz")) > 0


def test_core_executor_has_no_plugin_specific_tool_ids() -> None:
    """Architecture guard (P2-1): the generic executor must not special-case tools.

    The only tool_id the core executor may reference is ``internal`` — the
    marker for core-internal DAG nodes. Plugin-specific logic belongs in the
    plugin (declarative DAG, contracts, internal handlers).
    """
    import re
    from pathlib import Path as _Path

    import abi.executor as executor_module

    source = _Path(executor_module.__file__).read_text(encoding="utf-8")
    comparisons = re.findall(r'tool_id\s*(?:!=|==)\s*"([a-z0-9_]+)"', source)
    offenders = sorted(set(comparisons) - {"internal"})
    assert offenders == [], (
        f"Plugin-specific tool_id literals leaked into the core executor: {offenders}"
    )


def test_control_plane_fields_never_reach_tool_params(tmp_path: Path) -> None:
    """P2-4: control-plane metadata lives on explicit PlanStep fields.

    The declarative contract/internal-handler/dag-node metadata must be
    readable via the schema accessors (with legacy params fallback) and must
    not leak into the merged parameter dict passed to ``skill.build_command``.
    """
    import json as jsonlib

    from abi.schemas import plan_step_contract, plan_step_dependencies, plan_step_internal_handler

    # Explicit fields serialize through to_dict (plan JSON round-trip).
    step = _step(
        step_id="S1_step",
        contract={"outputs": {"result": {"type": "file"}}},
        internal_handler={"handler_id": "h", "execution_scope": "worker"},
        dag_node_id="node_a",
        explicit_dependencies=["node_0"],
        batch_cleanup=True,
    )
    payload = jsonlib.loads(jsonlib.dumps(step.to_dict()))
    assert payload["contract"] == {"outputs": {"result": {"type": "file"}}}
    assert payload["dag_node_id"] == "node_a"
    assert payload["batch_cleanup"] is True

    # Accessors prefer the explicit fields.
    assert plan_step_contract(step) == {"outputs": {"result": {"type": "file"}}}
    assert plan_step_internal_handler(step) == {"handler_id": "h", "execution_scope": "worker"}
    assert plan_step_dependencies(step) == ["node_0"]

    # Legacy serialized plans (params-based) still audit via the fallback.
    legacy = _step(params={"_contract": {"legacy": True}, "_dag_node_id": "node_b"})
    assert plan_step_contract(legacy) == {"legacy": True}

    # The executor's merged params carry no control-plane keys.
    executor = _executor(tmp_path)
    merged = executor._params_for_step(step, dry_run=False)
    for key in ("_contract", "_internal_handler", "_explicit_dependencies", "_dag_node_id"):
        assert key not in merged, key
    assert not any(k.startswith("_contract") for k in merged)


# ── Resume identity binding (WP3) ────────────────────────────────────────────


def test_resume_refuses_reuse_when_output_checksum_changed(tmp_path: Path) -> None:
    output = tmp_path / "result.tsv"
    output.write_text("value\n1\n", encoding="utf-8")
    skill = _Skill()
    executor = _executor(tmp_path, skill=skill)
    executor._prior_checksums = {str(output): "sha256:" + "0" * 64}
    step = _step(
        outputs={"result": str(output), "output_dir": str(tmp_path)},
        params={"_contract": {"outputs": {"result": {"type": "file"}}}},
    )

    row, error = executor._execute_step(
        step,
        dry_run=False,
        resume=True,
        provenance=tmp_path / "provenance",
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )

    assert error is None
    assert row["status"] == "success"
    assert "resume reuse rejected" in row["reason"]
    assert "checksum mismatch" in row["reason"]
    assert skill.params is not None  # re-executed instead of reused


def test_resume_refuses_reuse_when_input_checksum_changed(tmp_path: Path) -> None:
    output = tmp_path / "result.tsv"
    output.write_text("value\n1\n", encoding="utf-8")
    upstream_input = tmp_path / "input.tsv"
    upstream_input.write_text("changed\n", encoding="utf-8")
    skill = _Skill()
    executor = _executor(tmp_path, skill=skill)
    executor._prior_checksums = {
        str(output): compute_file_checksum(output),
        str(upstream_input): "sha256:" + "1" * 64,  # recorded digest no longer matches
    }
    step = _step(
        inputs={"table": str(upstream_input)},
        outputs={"result": str(output), "output_dir": str(tmp_path)},
        params={"_contract": {"outputs": {"result": {"type": "file"}}}},
    )

    row, error = executor._execute_step(
        step,
        dry_run=False,
        resume=True,
        provenance=tmp_path / "provenance",
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )

    assert error is None
    assert row["status"] == "success"
    assert "resume reuse rejected" in row["reason"]
    assert "input changed" in row["reason"]
    assert skill.params is not None


def test_resume_reuses_step_when_prior_checksums_match(tmp_path: Path) -> None:
    output = tmp_path / "result.tsv"
    output.write_text("value\n1\n", encoding="utf-8")
    skill = _Skill()
    executor = _executor(tmp_path, skill=skill)
    executor._prior_checksums = {str(output): compute_file_checksum(output)}
    step = _step(
        outputs={"result": str(output), "output_dir": str(tmp_path)},
        params={"_contract": {"outputs": {"result": {"type": "file"}}}},
    )

    row, error = executor._execute_step(
        step,
        dry_run=False,
        resume=True,
        provenance=tmp_path / "provenance",
        tables_dir=tmp_path / "tables",
        progress_recorder=None,
    )

    assert error is None
    assert row["status"] == "resumed"
    assert skill.params is None


def test_resume_run_carries_prior_checksum_chain_and_reruns_tampered_output(tmp_path: Path) -> None:
    """WP3: resume binds reused artifacts to the prior run's recorded identity."""
    outdir = tmp_path / "out"
    output = outdir / "steps" / "s1" / "result.tsv"
    output.parent.mkdir(parents=True)

    def _plan() -> ExecutionPlan:
        return ExecutionPlan(
            project_name="resume-binding",
            mode="auto",
            threads=1,
            outdir=str(outdir),
            log_dir=str(tmp_path / "log"),
            samples=[SampleInput(sample_id="S1")],
            sample_context=SampleContext([SampleInput(sample_id="S1")], True, False),
            steps=[
                PlanStep(
                    step_id="s1",
                    step_name="S1",
                    tool_id="tool",
                    category="test",
                    sample_id="S1",
                    inputs={},
                    outputs={"result": str(output), "output_dir": str(output.parent)},
                    params={"_contract": {"outputs": {"result": {"contract": {"type": "file"}}}}},
                )
            ],
            selected_tools=["tool"],
            analysis_type="test",
        )

    class _WritingSkill:
        def __init__(self) -> None:
            self.content = "value\n1\n"
            self.calls = 0

        def build_command(self, params):
            return ["tool"]

        def run(self, params, *, dry_run: bool):
            self.calls += 1
            Path(str(params["result"])).write_text(self.content, encoding="utf-8")
            return SimpleNamespace(return_code=0, status="success", outputs={})

    first_skill = _WritingSkill()
    executor = _executor(tmp_path, skill=first_skill)
    executor.run(_plan(), {"outdir": str(outdir), "log_dir": str(tmp_path / "log")})
    first_summary = json.loads(
        (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )
    recorded = json.loads((outdir / "provenance" / "checksums.json").read_text(encoding="utf-8"))
    assert str(output) in recorded

    # Tamper with the completed step's output, then resume: the recorded
    # identity no longer matches, so the step must re-execute.
    # 篡改已完成步骤的产物后恢复：记录身份不再匹配，步骤必须重跑。
    output.write_text("tampered\n", encoding="utf-8")
    tamper_skill = _WritingSkill()
    tamper_skill.content = "fresh\n"
    executor_tamper = _executor(tmp_path, skill=tamper_skill)
    executor_tamper.run(
        _plan(),
        {"outdir": str(outdir), "log_dir": str(tmp_path / "log")},
        resume=True,
    )
    second_summary = json.loads(
        (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert second_summary["resumes_run_id"] == first_summary["run_id"]
    assert tamper_skill.calls == 1  # re-executed, not reused

    commands = (outdir / "provenance" / "commands.tsv").read_text(encoding="utf-8")
    assert "resume reuse rejected" in commands
    assert "checksum mismatch" in commands
    # The refreshed checksum chain records the new content for downstream runs.
    refreshed = json.loads((outdir / "provenance" / "checksums.json").read_text(encoding="utf-8"))
    assert refreshed[str(output)] != recorded[str(output)]
