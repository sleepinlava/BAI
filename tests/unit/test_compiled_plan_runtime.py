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


# ── Confirmed-plan binding and run identity (WP4/B1) ─────────────────────────


def test_plan_response_includes_confirmed_plan_id(tmp_path):
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
    persisted = json.loads((outdir / "compiled_plan.json").read_text(encoding="utf-8"))
    assert payload["result"]["plan_id"] == persisted["plan_id"]
    assert persisted["plan_id"].startswith("sha256:")


def test_run_records_confirmed_plan_identity_in_run_summary(tmp_path):
    outdir = tmp_path / "results"

    agent = ABIAgentInterface()
    plan_payload = json.loads(
        agent.plan(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            check_files=False,
        )
    )
    confirmed_before = (outdir / "compiled_plan.json").read_bytes()

    run_payload = json.loads(
        agent.run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            confirm_execution=True,
            check_files=False,
        )
    )

    assert run_payload["status"] == "success"
    summary = json.loads((outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["plan_id"] == plan_payload["result"]["plan_id"]
    # The confirmed plan artifact is evidence: the run verifies against it and
    # must not rewrite it.
    # 已确认计划产物是证据：运行对它验证，且不得改写。
    assert (outdir / "compiled_plan.json").read_bytes() == confirmed_before


def test_run_without_prior_plan_binds_compiled_plan(tmp_path):
    outdir = tmp_path / "results"

    payload = json.loads(
        ABIAgentInterface().run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            confirm_execution=True,
            check_files=False,
        )
    )

    assert payload["status"] == "success"
    persisted = json.loads((outdir / "compiled_plan.json").read_text(encoding="utf-8"))
    summary = json.loads((outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["plan_id"] == persisted["plan_id"]


def test_run_refuses_drift_after_confirmation(tmp_path):
    outdir = tmp_path / "results"

    agent = ABIAgentInterface()
    agent.plan(
        analysis_type="metatranscriptomics",
        outdir=str(outdir),
        log_dir=str(tmp_path / "logs"),
        check_files=False,
    )
    confirmed_before = (outdir / "compiled_plan.json").read_bytes()

    payload = json.loads(
        agent.run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            threads=2,  # drifts from the confirmed plan
            confirm_execution=True,
            check_files=False,
        )
    )

    assert payload["status"] == "error"
    assert payload["error_code"] == "invalid_config"
    assert "drift" in payload["error"].lower()
    assert "abi plan" in payload["diagnostic_hints"][0]["suggested_next_action"]
    # No unapproved work: no execution artifacts, confirmed plan untouched.
    # 未批准的工作没有启动：无执行产物，已确认计划未被改写。
    assert not (outdir / "provenance" / "run_summary.json").exists()
    assert (outdir / "compiled_plan.json").read_bytes() == confirmed_before


def test_resume_links_previous_run_and_archives_history(tmp_path):
    outdir = tmp_path / "results"

    agent = ABIAgentInterface()
    agent.plan(
        analysis_type="metatranscriptomics",
        outdir=str(outdir),
        log_dir=str(tmp_path / "logs"),
        check_files=False,
    )
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
    first_commands = (outdir / "provenance" / "commands.tsv").read_text(encoding="utf-8")

    second = json.loads(
        agent.run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            resume=True,
            confirm_execution=True,
            check_files=False,
        )
    )
    assert second["status"] == "success"
    second_summary = json.loads(
        (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )

    # The resume is an independent run record linked to the prior run.
    # 恢复是独立的运行记录，并通过 resumes_run_id 关联先前运行。
    assert second_summary["run_id"] != first_summary["run_id"]
    assert second_summary["resumes_run_id"] == first_summary["run_id"]
    archive = outdir / "provenance" / second_summary["previous_run_archive"]
    assert (archive / "run_summary.json").is_file()
    assert (
        json.loads((archive / "run_summary.json").read_text(encoding="utf-8"))["run_id"]
        == (first_summary["run_id"])
    )
    assert (archive / "commands.tsv").read_text(encoding="utf-8") == first_commands


def test_rerun_without_resume_archives_history_without_resume_link(tmp_path):
    outdir = tmp_path / "results"

    agent = ABIAgentInterface()
    agent.plan(
        analysis_type="metatranscriptomics",
        outdir=str(outdir),
        log_dir=str(tmp_path / "logs"),
        check_files=False,
    )
    agent.run(
        analysis_type="metatranscriptomics",
        outdir=str(outdir),
        log_dir=str(tmp_path / "logs"),
        smoke=True,
        confirm_execution=True,
        check_files=False,
    )
    first_summary = json.loads(
        (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )

    payload = json.loads(
        agent.run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            confirm_execution=True,
            check_files=False,
        )
    )
    assert payload["status"] == "success"
    second_summary = json.loads(
        (outdir / "provenance" / "run_summary.json").read_text(encoding="utf-8")
    )
    assert second_summary["resumes_run_id"] is None
    archive = outdir / "provenance" / second_summary["previous_run_archive"]
    prior = json.loads((archive / "run_summary.json").read_text(encoding="utf-8"))
    assert prior["run_id"] == first_summary["run_id"]


def test_run_writes_audit_snapshot(tmp_path):
    """WP5: execution persists the audit snapshot for plugin-free audit."""
    outdir = tmp_path / "results"

    payload = json.loads(
        ABIAgentInterface().run(
            analysis_type="metatranscriptomics",
            outdir=str(outdir),
            log_dir=str(tmp_path / "logs"),
            smoke=True,
            confirm_execution=True,
            check_files=False,
        )
    )
    assert payload["status"] == "success"

    snapshot = json.loads(
        (outdir / "provenance" / "audit_snapshot.json").read_text(encoding="utf-8")
    )
    assert snapshot["schema_version"] == "abi.audit_snapshot.v1"
    assert snapshot["analysis_type"] == "metatranscriptomics"
    assert snapshot["limitations"], "plugin-declared limitations must be captured"
    assert snapshot["standard_table_schemas"]
    assert snapshot["abi_version"]
