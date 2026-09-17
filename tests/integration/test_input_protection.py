from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from abi.executor import GenericABIExecutor
from abi.provenance import RunLogger
from abi.schemas import ExecutionPlan, PlanStep, SampleContext, SampleInput, ToolError
from abi.tables import StandardTableManager


class _FailingSkill:
    def check_installation(self) -> bool:
        return True

    def capture_version(self) -> str:
        return "test-tool 1.0"

    def build_command(self, params):
        return ["test-tool", str(params.get("output_dir", ""))]

    def run(self, params, *, dry_run: bool):
        del params, dry_run
        return SimpleNamespace(return_code=9, outputs={})


class _FailingRegistry:
    def has(self, tool_id: str) -> bool:
        return tool_id == "failing_tool"

    def get(self, tool_id: str, *, mock_tools: bool = False):
        del tool_id, mock_tools
        return {}

    def list_tools(self):
        return [{"id": "failing_tool", "executable": "test-tool"}]

    def check_tools(self, *, mock_tools: bool = False, config=None):
        del mock_tools, config
        return []

    def create(self, tool_id: str, *, mock_tools: bool = False):
        del mock_tools
        if tool_id != "failing_tool":
            raise AssertionError(f"unexpected tool: {tool_id}")
        return _FailingSkill()


def test_executor_failed_cleanup_derives_and_preserves_sample_input(tmp_path: Path) -> None:
    outdir = tmp_path / "result"
    output_dir = outdir / "01_preprocessing/S1"
    output_dir.mkdir(parents=True)
    raw_target = tmp_path / "source" / "S1_R1.fastq.gz"
    raw_target.parent.mkdir(parents=True)
    raw_target.write_bytes(b"original read")
    raw_link = output_dir / "S1_R1.fastq.gz"
    raw_link.symlink_to(raw_target)
    partial = output_dir / "partial.tmp"
    partial.write_bytes(b"partial tool output")

    sample = SampleInput(sample_id="S1", platform="illumina", read1=str(raw_link))
    step = PlanStep(
        step_id="failing_step",
        step_name="Failing step",
        tool_id="failing_tool",
        category="test",
        sample_id="S1",
        outputs={"output_dir": str(output_dir)},
        params={"_cleanup_failed_output_dir": True},
    )
    plan = ExecutionPlan(
        project_name="input-protection",
        mode="auto",
        threads=1,
        outdir=str(outdir),
        log_dir=str(tmp_path / "logs"),
        samples=[sample],
        steps=[step],
        selected_tools=["failing_tool"],
        sample_context=SampleContext([sample], False, False),
    )
    executor = GenericABIExecutor(
        _FailingRegistry(),
        RunLogger(tmp_path / "logs"),
        table_manager=StandardTableManager({"summary": ["sample_id"]}),
        parse_outputs=lambda *args: {},
    )

    with pytest.raises(ToolError):
        executor.run(
            plan,
            {"outdir": str(outdir), "execution": {"progress": False}},
        )

    assert raw_link.is_symlink()
    assert raw_link.read_bytes() == b"original read"
    assert not partial.exists()
