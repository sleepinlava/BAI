"""P1-3: resolved-path propagation must behave identically in serial and parallel.

The serial branch of ``GenericABIExecutor.run`` propagates resolved output
paths to downstream steps (B36 fix).  The parallel branch historically skipped
propagation entirely, so per-sample chains and cross-sample steps received
stale abstract paths.  These tests pin the desired behavior for both modes.
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

from abi.executor import GenericABIExecutor
from abi.provenance import RunLogger
from abi.schemas import ExecutionPlan, SampleContext, SampleInput
from abi.tables import StandardTableManager


class _WriterSkill:
    """Fake tool: writes an output file whose name differs from the plan."""

    def build_command(self, params):
        return ["writer", "--outdir", str(params.get("output_dir", ""))]

    def run(self, params, *, dry_run: bool):
        output_dir = Path(str(params["output_dir"]))
        output_dir.mkdir(parents=True, exist_ok=True)
        sample_id = str(params.get("sample_id", "S1"))
        actual = output_dir / f"{sample_id}_result.tsv"
        actual.write_text("col\n1\n", encoding="utf-8")
        return SimpleNamespace(return_code=0, status="success", outputs={})


class _ConsumerSkill:
    """Fake tool: records the input paths it was invoked with."""

    def __init__(self, captured: list, lock: threading.Lock) -> None:
        self._captured = captured
        self._lock = lock

    def build_command(self, params):
        return ["consumer", "--data", str(params.get("data", ""))]

    def run(self, params, *, dry_run: bool):
        with self._lock:
            self._captured.append(str(params["data"]))
        return SimpleNamespace(return_code=0, status="success", outputs={})


class _Registry:
    def __init__(self, consumer_captured: list, lock: threading.Lock) -> None:
        self._consumer_captured = consumer_captured
        self._lock = lock

    def has(self, tool_id: str) -> bool:
        return tool_id in {"writer", "consumer"}

    def get(self, tool_id: str) -> dict:
        return {"id": tool_id}

    def list_tools(self) -> list:
        return [{"id": "writer"}, {"id": "consumer"}]

    def check_tools(self, *, mock_tools: bool = False, config=None) -> list:
        return []

    def create(self, tool_id: str, *, mock_tools: bool = False):
        if tool_id == "writer":
            return _WriterSkill()
        return _ConsumerSkill(self._consumer_captured, self._lock)


def _plan(tmp_path: Path, *, outdir: Path) -> ExecutionPlan:
    samples = [
        SampleInput(sample_id="S1", platform="illumina"),
        SampleInput(sample_id="S2", platform="illumina"),
    ]
    context = SampleContext(samples, True, False, True, False)

    def writer_step(sample_id: str):
        return dict(
            step_id=f"{sample_id}_writer",
            step_name=f"{sample_id} writer",
            tool_id="writer",
            category="test",
            sample_id=sample_id,
            inputs={"sample_id": sample_id},
            outputs={
                "output_dir": str(outdir / "detection" / sample_id),
                "result": str(outdir / "detection" / sample_id / f"{sample_id}_result.planned.tsv"),
            },
            params={
                "_contract": {
                    "outputs": {"result": {"type": "file", "format": "tsv"}},
                }
            },
        )

    def consumer_step(sample_id: str):
        return dict(
            step_id=f"{sample_id}_consumer",
            step_name=f"{sample_id} consumer",
            tool_id="consumer",
            category="test",
            sample_id=sample_id,
            inputs={
                "data": str(
                    outdir / "detection" / f"{sample_id}_consumer" / f"{sample_id}_input.tsv"
                )
            },
            outputs={},
        )

    steps = [
        _plan_step(writer_step("S1")),
        _plan_step(consumer_step("S1")),
        _plan_step(writer_step("S2")),
        _plan_step(consumer_step("S2")),
        _plan_step(
            dict(
                step_id="merge_cross",
                step_name="Cross-sample consumer",
                tool_id="consumer",
                category="test",
                sample_id=None,
                inputs={"data": str(outdir / "detection" / "S1_consumer" / "S1_input.tsv")},
                outputs={},
            )
        ),
    ]
    return ExecutionPlan(
        project_name="propagation",
        mode="auto",
        threads=1,
        outdir=str(outdir.parent),
        log_dir=str(tmp_path / "logs"),
        samples=samples,
        sample_context=context,
        selected_tools=[],
        steps=steps,
    )


def _plan_step(values: dict):
    from abi.schemas import PlanStep

    return PlanStep(**values)


def _run(tmp_path: Path, *, parallel: bool) -> tuple[list, Path]:
    outdir = tmp_path / "out" / "pipeline"
    captured: list = []
    lock = threading.Lock()
    executor = GenericABIExecutor(
        _Registry(captured, lock),
        RunLogger(tmp_path / "logs"),
        table_manager=StandardTableManager({"summary": ["sample_id"]}),
        parse_outputs=lambda *args: {},
    )
    plan = _plan(tmp_path, outdir=outdir)
    config = {
        "outdir": str(outdir.parent),
        "execution": {
            "parallel": parallel,
            "workers": 2,
            "progress": False,
        },
    }
    executor.run(plan, config, dry_run=False)
    return captured, outdir


def test_parallel_mode_propagates_resolved_paths_within_chains(tmp_path):
    captured, outdir = _run(tmp_path, parallel=True)

    resolved_s1 = str(outdir / "detection" / "S1" / "S1_result.tsv")
    resolved_s2 = str(outdir / "detection" / "S2" / "S2_result.tsv")
    assert resolved_s1 in captured, captured
    assert resolved_s2 in captured, captured
    # The stale planned path must not reach any consumer.
    planned = [c for c in captured if c.endswith("planned.tsv")]
    assert planned == [], planned


def test_parallel_mode_propagates_resolved_paths_to_cross_sample_steps(tmp_path):
    captured, outdir = _run(tmp_path, parallel=True)

    # The cross-sample consumer (last captured entry: runs after chains)
    # receives the resolved S1 output, not the planned abstract path.
    assert str(outdir / "detection" / "S1" / "S1_result.tsv") in captured


def test_serial_mode_parity_with_parallel_propagation(tmp_path):
    captured, outdir = _run(tmp_path, parallel=False)

    resolved_s1 = str(outdir / "detection" / "S1" / "S1_result.tsv")
    resolved_s2 = str(outdir / "detection" / "S2" / "S2_result.tsv")
    assert resolved_s1 in captured, captured
    assert resolved_s2 in captured, captured
    planned = [c for c in captured if c.endswith("planned.tsv")]
    assert planned == [], planned
