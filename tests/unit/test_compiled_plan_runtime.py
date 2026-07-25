"""Tests for CompiledPlan runtime wiring through ABIAgentInterface.plan()."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from abi.agent import ABIAgentInterface


def _stub_plan(steps: list, outdir: Path) -> SimpleNamespace:
    """Create a lightweight stub matching ExecutionPlan's interface."""
    return SimpleNamespace(
        project_name="test",
        mode="auto",
        threads=4,
        outdir=str(outdir),
        steps=steps,
        selected_tools=["fastp"],
        analysis_type="metatranscriptomics",
        samples=None,
        log_dir=str(outdir / "logs"),
    )


def _stub_step(step_id: str, outdir: Path, params: dict | None = None) -> SimpleNamespace:
    """Create a lightweight stub matching PlanStep's interface."""
    return SimpleNamespace(
        step_id=step_id,
        tool_id="fastp",
        category="qc",
        sample_id="sample1",
        inputs={},
        outputs={"output_dir": str(outdir / "qc" / step_id)},
        params=params or {},
        skipped=False,
        reason=None,
    )


def _patch_prepared_plan(monkeypatch, plan: SimpleNamespace, outdir: Path) -> None:
    """Force ``_build_plan`` to return *plan* via a stubbed coordinator."""
    prepared = SimpleNamespace(plugin=object(), config={"outdir": str(outdir)}, plan=plan)

    class _StubCoordinator:
        def prepare(self, *args, **kwargs):
            return prepared

    monkeypatch.setattr("abi.agent.interface.WorkflowCoordinator", _StubCoordinator)


def test_plan_persists_compiled_plan_json(tmp_path):
    outdir = tmp_path / "results"

    payload = json.loads(
        ABIAgentInterface().plan(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            check_files=False,
        )
    )

    assert payload["status"] == "success"
    compiled_path = outdir / "compiled_plan.json"
    assert compiled_path.exists()
    compiled = json.loads(compiled_path.read_text(encoding="utf-8"))
    assert compiled["schema_version"] == "abi.compiled_plan.v1"
    assert compiled["analysis_type"] == "metatranscriptomics"
    assert len(compiled["steps"]) == payload["result"]["steps"]
    assert compiled["enabled_steps"] == sorted(step["step_id"] for step in compiled["steps"])
    kinds = {step["execution_kind"] for step in compiled["steps"]}
    assert kinds <= {"external", "internal_worker", "internal_driver"}


def test_plan_invariant_violation_returns_structured_error(monkeypatch, tmp_path):
    """A declaration violating plan invariants aborts plan() with an error envelope."""
    outdir = tmp_path / "results"
    steps = [
        _stub_step("dup", outdir),
        _stub_step("dup", outdir),  # duplicate step_id violates a plan invariant
    ]
    _patch_prepared_plan(monkeypatch, _stub_plan(steps, outdir), outdir)

    payload = json.loads(
        ABIAgentInterface(verbose_errors=True).plan(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            check_files=False,
        )
    )

    assert payload["status"] == "error"
    assert payload["command"] == "plan"
    assert payload["error_type"] == "PlanIntegrityError"
    assert payload["error_code"] == "invalid_config"
    assert "Duplicate step_id" in payload["error"]
    assert payload["diagnostic_hints"]
    # Nothing is persisted when compilation aborts planning.
    assert not (outdir / "execution_plan.json").exists()
    assert not (outdir / "compiled_plan.json").exists()


def test_plan_undefined_dependency_returns_structured_error(monkeypatch, tmp_path):
    outdir = tmp_path / "results"
    steps = [
        _stub_step("s1", outdir, params={"_explicit_dependencies": ["nonexistent"]}),
    ]
    _patch_prepared_plan(monkeypatch, _stub_plan(steps, outdir), outdir)

    payload = json.loads(
        ABIAgentInterface(verbose_errors=True).plan(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            check_files=False,
        )
    )

    assert payload["status"] == "error"
    assert payload["error_type"] == "PlanIntegrityError"
    assert payload["error_code"] == "invalid_config"
    assert "undefined step" in payload["error"]
    assert not (outdir / "execution_plan.json").exists()
