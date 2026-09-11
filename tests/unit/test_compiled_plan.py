"""Tests for CompiledPlan — compilation, invariants, resource resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from abi.errors import PlanDriftError, PlanIntegrityError, ToolResolutionError
from abi.execution_policy import ExecutionPolicy, ResourceOverride
from abi.tool_catalog import ToolCatalog
from abi.tools import ResourceSpec
from abi.workflow.compiled_plan import (
    CompilationWarning,
    CompiledPlan,
    CompiledStep,
    ExecutionKind,
    _validate_invariants,
    bind_confirmed_plan,
    compile_plan,
    load_compiled_plan,
    write_compiled_plan,
)

# ── Test helpers ─────────────────────────────────────────────────────────────


def _plan_step(
    step_id: str,
    tool_id: str = "fastp",
    category: str = "qc",
    sample_id: str | None = "sample1",
    outputs: dict | None = None,
    params: dict | None = None,
    skipped: bool = False,
) -> "object":
    """Create a lightweight stub matching PlanStep's interface."""
    from types import SimpleNamespace

    return SimpleNamespace(
        step_id=step_id,
        tool_id=tool_id,
        category=category,
        sample_id=sample_id,
        inputs={},
        outputs=outputs or {"output_dir": f"/tmp/out/{category}/{sample_id}"},
        params=params or {},
        skipped=skipped,
        reason=None,
    )


def _exec_plan(
    steps: list,
    *,
    outdir: str = "/tmp/out",
    project_name: str = "test",
    mode: str = "auto",
    threads: int = 4,
    selected_tools: list | None = None,
    analysis_type: str = "metagenomic_plasmid",
) -> "object":
    """Create a lightweight stub matching ExecutionPlan's interface."""
    from types import SimpleNamespace

    return SimpleNamespace(
        project_name=project_name,
        mode=mode,
        threads=threads,
        outdir=outdir,
        steps=steps,
        selected_tools=selected_tools or ["fastp"],
        analysis_type=analysis_type,
        samples=None,
        log_dir="/tmp/out/logs",
    )


# ── ExecutionKind ────────────────────────────────────────────────────────────


class TestExecutionKind:
    def test_values(self) -> None:
        assert ExecutionKind.EXTERNAL.value == "external"
        assert ExecutionKind.INTERNAL_WORKER.value == "internal_worker"
        assert ExecutionKind.INTERNAL_DRIVER.value == "internal_driver"

    def test_is_string(self) -> None:
        assert ExecutionKind.EXTERNAL == "external"
        assert isinstance(ExecutionKind.EXTERNAL, str)


# ── CompiledStep ─────────────────────────────────────────────────────────────


class TestCompiledStep:
    def test_minimal(self) -> None:
        s = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
        )
        assert s.step_id == "s1"
        assert s.dependencies == ()
        assert s.resources.cpu == 1
        assert s.env_name == ""

    def test_nested_containers_are_immutable(self) -> None:
        """WP4: nested lists, dicts, and resource objects cannot be mutated."""
        s = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
            dependencies=["a"],
            inputs={"x": 1},
            resources=ResourceSpec(cpu=4),
        )
        with pytest.raises(AttributeError):
            s.dependencies.append("b")
        with pytest.raises(TypeError):
            s.inputs["y"] = 2
        with pytest.raises(AttributeError):
            s.params.clear()
        with pytest.raises(Exception):
            s.resources.cpu = 9
        with pytest.raises(Exception):
            s.step_id = "s2"

    def test_with_resources(self) -> None:
        s = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
            resources=ResourceSpec(cpu=8, memory="16GB"),
            env_name="autoplasm-qc",
        )
        assert s.resources.cpu == 8
        assert s.resources.memory == "16GB"
        assert s.env_name == "autoplasm-qc"


# ── CompiledPlan ─────────────────────────────────────────────────────────────


class TestCompiledPlan:
    def test_empty(self) -> None:
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=[],
        )
        assert len(cp.steps) == 0
        assert cp.step_ids == []

    def test_get(self) -> None:
        cs = CompiledStep(
            step_id="a",
            tool_id="x",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
        )
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=[cs],
        )
        assert cp.get("a") is cs
        with pytest.raises(KeyError):
            cp.get("b")

    def test_classification(self) -> None:
        steps = [
            CompiledStep("e", "fastp", "qc", None, ExecutionKind.EXTERNAL),
            CompiledStep("w", "internal", "merge", None, ExecutionKind.INTERNAL_WORKER),
            CompiledStep("d", "internal", "setup", None, ExecutionKind.INTERNAL_DRIVER),
        ]
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=steps,
        )
        assert len(cp.external_steps) == 1
        assert len(cp.internal_worker_steps) == 1
        assert len(cp.internal_driver_steps) == 1


# ── compile_plan ─────────────────────────────────────────────────────────────


class TestCompilePlan:
    def test_smoke_external_step(self, tmp_path: Path) -> None:
        """Compile a trivial external-step plan."""
        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step(
            "sample1_qc_fastp", outputs={"output_dir": str(outdir / "qc" / "sample1")}
        )
        plan = _exec_plan([step], outdir=str(outdir))
        from abi.tool_catalog import RuntimeToolDescriptor

        compiled = compile_plan(
            plan,
            catalog=ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")]),
            outdir=outdir,
        )
        assert len(compiled.steps) == 1
        cs = compiled.steps[0]
        assert cs.step_id == "sample1_qc_fastp"
        assert cs.execution_kind == ExecutionKind.EXTERNAL

    def test_skipped_steps_excluded(self, tmp_path: Path) -> None:
        outdir = tmp_path / "output"
        outdir.mkdir()
        steps = [
            _plan_step("s1", outputs={"output_dir": str(outdir / "qc" / "s1")}),
            _plan_step("s2", outputs={"output_dir": str(outdir / "qc" / "s2")}, skipped=True),
        ]
        plan = _exec_plan(steps, outdir=str(outdir))
        from abi.tool_catalog import RuntimeToolDescriptor

        compiled = compile_plan(
            plan,
            catalog=ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")]),
            outdir=outdir,
        )
        assert len(compiled.steps) == 1
        assert compiled.steps[0].step_id == "s1"

    def test_internal_worker(self, tmp_path: Path) -> None:
        outdir = tmp_path / "output"
        outdir.mkdir()
        handler = _make_handler("worker")
        step = _plan_step(
            "s1",
            tool_id="internal",
            outputs={"output_dir": str(outdir / "merge" / "sample1")},
            params={"_internal_handler": handler},
        )
        plan = _exec_plan([step], outdir=str(outdir))
        compiled = compile_plan(plan, catalog=ToolCatalog(), outdir=outdir)
        assert compiled.steps[0].execution_kind == ExecutionKind.INTERNAL_WORKER

    def test_internal_driver(self, tmp_path: Path) -> None:
        outdir = tmp_path / "output"
        outdir.mkdir()
        handler = _make_handler("driver")
        step = _plan_step(
            "driver_hdf5_build",
            tool_id="internal",
            outputs={"output_dir": str(outdir / "driver_output")},
            params={"_internal_handler": handler},
            sample_id=None,
        )
        plan = _exec_plan([step], outdir=str(outdir))
        compiled = compile_plan(plan, catalog=ToolCatalog(), outdir=outdir)
        assert compiled.steps[0].execution_kind == ExecutionKind.INTERNAL_DRIVER

    def test_path_escape_rejected(self, tmp_path: Path) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step(
            "bad",
            outputs={"output_dir": "/etc/passwd"},
        )
        plan = _exec_plan([step], outdir=str(outdir))
        with pytest.raises(PlanIntegrityError, match="escapes"):
            compile_plan(
                plan,
                catalog=ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")]),
                outdir=outdir,
            )

    def test_unknown_external_tool_is_rejected(self, tmp_path: Path) -> None:
        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step("unknown", tool_id="not_registered", outputs={})
        plan = _exec_plan([step], outdir=str(outdir))

        with pytest.raises(ToolResolutionError, match="not_registered"):
            compile_plan(plan, catalog=ToolCatalog(), outdir=outdir)

    def test_every_output_path_is_validated(self, tmp_path: Path) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step(
            "bad",
            outputs={"output_dir": str(outdir / "safe"), "report": "/etc/passwd"},
        )
        plan = _exec_plan([step], outdir=str(outdir))

        with pytest.raises(PlanIntegrityError, match="report"):
            compile_plan(
                plan,
                catalog=ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")]),
                outdir=outdir,
            )

    def test_similar_prefix_path_is_rejected(self, tmp_path: Path) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step("bad", outputs={"report": str(tmp_path / "output-escape" / "x")})
        plan = _exec_plan([step], outdir=str(outdir))

        with pytest.raises(PlanIntegrityError, match="escapes"):
            compile_plan(
                plan,
                catalog=ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")]),
                outdir=outdir,
            )

    def test_registry_tool_with_catalog(self, tmp_path: Path) -> None:
        """Compile with a catalog that knows about the tool."""
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        desc = RuntimeToolDescriptor(
            tool_id="fastp",
            name="FastP",
            env_name="autoplasm-qc",
            resources=ResourceSpec(cpu=4, memory="8GB"),
        )
        catalog = ToolCatalog([desc])
        step = _plan_step(
            "sample1_qc_fastp", outputs={"output_dir": str(outdir / "qc" / "sample1")}
        )
        plan = _exec_plan([step], outdir=str(outdir))
        compiled = compile_plan(plan, catalog=catalog, outdir=outdir)
        cs = compiled.steps[0]
        assert cs.resources.cpu == 4
        assert cs.env_name == "autoplasm-qc"

    def test_policy_applied(self, tmp_path: Path) -> None:
        """Policy invocation override wins over catalog."""
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        desc = RuntimeToolDescriptor(
            tool_id="fastp",
            resources=ResourceSpec(cpu=4, memory="8GB"),
        )
        catalog = ToolCatalog([desc])
        policy = ExecutionPolicy(
            invocation_overrides=ResourceOverride(cpu=2, memory="4GB"),
        )
        step = _plan_step("s1", outputs={"output_dir": str(outdir / "qc" / "s1")})
        plan = _exec_plan([step], outdir=str(outdir))
        compiled = compile_plan(plan, catalog=catalog, policy=policy, outdir=outdir)
        cs = compiled.steps[0]
        assert cs.resources.cpu == 2
        assert cs.resources.memory == "4GB"


# ── Invariant checks ─────────────────────────────────────────────────────────


class TestInvariants:
    def test_missing_dependency(self) -> None:
        cs = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
            dependencies=["nonexistent"],
        )
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=[cs],
            enabled_steps=["s1"],
        )
        with pytest.raises(PlanIntegrityError, match="undefined step"):
            _validate_invariants(cp, {"s1"})

    def test_self_dependency(self) -> None:
        cs = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
            dependencies=["s1"],
        )
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=[cs],
            enabled_steps=["s1"],
        )
        with pytest.raises(PlanIntegrityError, match="depends on itself"):
            _validate_invariants(cp, {"s1"})

    def test_cycle(self) -> None:
        a = CompiledStep(
            step_id="a",
            tool_id="x",
            category="c",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
            dependencies=["b"],
        )
        b = CompiledStep(
            step_id="b",
            tool_id="y",
            category="c",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
            dependencies=["a"],
        )
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=[a, b],
            enabled_steps=["a", "b"],
        )
        with pytest.raises(PlanIntegrityError, match="Cycle"):
            _validate_invariants(cp, {"a", "b"})

    def test_mismatched_enabled(self) -> None:
        cs = CompiledStep(
            step_id="a",
            tool_id="x",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
        )
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=[cs],
            enabled_steps=["a", "b"],  # b not in steps
        )
        with pytest.raises(PlanIntegrityError, match="missing"):
            _validate_invariants(cp, {"a", "b"})


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_handler(scope: str) -> "object":
    """Create a stub internal handler with execution_scope."""
    from types import SimpleNamespace

    return SimpleNamespace(handler_id="test_handler", execution_scope=scope)


# ── Serialization, identity, and confirmed-plan binding (WP4) ────────────────


class TestPlanIdentity:
    def test_compile_assigns_deterministic_plan_id(self, tmp_path: Path) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step("s1", outputs={"output_dir": str(outdir / "qc" / "s1")})
        plan = _exec_plan([step], outdir=str(outdir))
        catalog = ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")])
        first = compile_plan(plan, catalog=catalog, outdir=outdir)
        second = compile_plan(plan, catalog=catalog, outdir=outdir)
        assert first.plan_id.startswith("sha256:")
        assert first.plan_id == second.plan_id == first.content_digest

    def test_plan_id_changes_when_plan_changes(self, tmp_path: Path) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        catalog = ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")])
        step_a = _plan_step("s1", outputs={"output_dir": str(outdir / "qc" / "s1")})
        step_b = _plan_step(
            "s1",
            outputs={"output_dir": str(outdir / "qc" / "s1")},
            params={"threads_flag": 8},
        )
        compiled_a = compile_plan(
            _exec_plan([step_a], outdir=str(outdir)), catalog=catalog, outdir=outdir
        )
        compiled_b = compile_plan(
            _exec_plan([step_b], outdir=str(outdir)), catalog=catalog, outdir=outdir
        )
        assert compiled_a.plan_id != compiled_b.plan_id

    def test_compiled_plan_is_deeply_frozen(self) -> None:
        cs = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
        )
        cp = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp"),
            steps=[cs],
            enabled_steps=["s1"],
        )
        with pytest.raises(AttributeError):
            cp.steps.append(cs)
        with pytest.raises(AttributeError):
            cp.enabled_steps.append("x")
        with pytest.raises(AttributeError):
            cp.selected_tools.append("y")


class TestSerializationRoundTrip:
    def test_round_trip_preserves_content(self, tmp_path: Path) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step(
            "s1",
            outputs={"output_dir": str(outdir / "qc" / "s1")},
            params={"keep": {"nested": [1, 2]}},
        )
        compiled = compile_plan(
            _exec_plan([step], outdir=str(outdir)),
            catalog=ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")]),
            outdir=outdir,
        )
        loaded = CompiledPlan.from_dict(compiled.to_dict())
        assert loaded.to_dict() == compiled.to_dict()
        assert loaded.plan_id == compiled.plan_id

    def test_round_trip_preserves_warnings(self, tmp_path: Path) -> None:
        cs = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
        )
        compiled = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=2,
            outdir=tmp_path,
            steps=[cs],
            enabled_steps=["s1"],
            warnings=[CompilationWarning(step_id="s1", message="note")],
            plan_id="",
        )
        loaded = CompiledPlan.from_dict(compiled.to_dict())
        assert loaded.to_dict() == compiled.to_dict()
        assert [w.message for w in loaded.warnings] == ["note"]

    def test_from_dict_rejects_unknown_schema_version(self) -> None:
        with pytest.raises(PlanIntegrityError, match="schema_version"):
            CompiledPlan.from_dict({"schema_version": "abi.compiled_plan.v999"})

    def test_from_dict_rejects_unknown_fields(self) -> None:
        data = {
            "schema_version": "abi.compiled_plan.v1",
            "plan_id": "",
            "project_name": "test",
            "analysis_type": "",
            "mode": "auto",
            "threads": 1,
            "outdir": "/tmp/out",
            "steps": [],
            "enabled_steps": [],
            "selected_tools": [],
            "warnings": [],
            "surprise_field": 1,
        }
        with pytest.raises(PlanIntegrityError, match="surprise_field"):
            CompiledPlan.from_dict(data)

    def test_from_dict_rejects_bad_execution_kind(self) -> None:
        data = {
            "schema_version": "abi.compiled_plan.v1",
            "plan_id": "",
            "project_name": "test",
            "analysis_type": "",
            "mode": "auto",
            "threads": 1,
            "outdir": "/tmp/out",
            "steps": [
                {
                    "step_id": "s1",
                    "tool_id": "fastp",
                    "category": "qc",
                    "execution_kind": "teleport",
                }
            ],
            "enabled_steps": ["s1"],
            "selected_tools": [],
            "warnings": [],
        }
        with pytest.raises(PlanIntegrityError, match="execution kind"):
            CompiledPlan.from_dict(data)

    def test_from_dict_rejects_tampered_plan_id(self) -> None:
        cs = CompiledStep(
            step_id="s1",
            tool_id="fastp",
            category="qc",
            sample_id=None,
            execution_kind=ExecutionKind.EXTERNAL,
        )
        compiled = CompiledPlan(
            project_name="test",
            mode="auto",
            threads=1,
            outdir=Path("/tmp/out"),
            steps=[cs],
            enabled_steps=["s1"],
            plan_id="sha256:0" * 1,
        )
        data = compiled.to_dict()
        data["plan_id"] = "sha256:" + "f" * 64
        with pytest.raises(PlanIntegrityError, match="identity mismatch"):
            CompiledPlan.from_dict(data)

    def test_load_compiled_plan_round_trips_file(self, tmp_path: Path) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step("s1", outputs={"output_dir": str(outdir / "qc" / "s1")})
        compiled = compile_plan(
            _exec_plan([step], outdir=str(outdir)),
            catalog=ToolCatalog([RuntimeToolDescriptor(tool_id="fastp")]),
            outdir=outdir,
        )
        path = write_compiled_plan(compiled, outdir / "compiled_plan.json")
        loaded = load_compiled_plan(path)
        assert loaded.to_dict() == compiled.to_dict()


class TestBindConfirmedPlan:
    def _prepared(self, tmp_path: Path, *, params: dict | None = None):
        from types import SimpleNamespace

        outdir = tmp_path / "output"
        outdir.mkdir()
        step = _plan_step(
            "s1",
            outputs={"output_dir": str(outdir / "qc" / "s1")},
            params=params or {},
        )
        plan = _exec_plan([step], outdir=str(outdir))
        return SimpleNamespace(plan=plan, config={"outdir": str(outdir)}), outdir

    def test_first_bind_persists_confirmed_plan(self, tmp_path, monkeypatch) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        prepared, outdir = self._prepared(tmp_path)

        class _Catalog(ToolCatalog):
            @classmethod
            def from_project_root(cls):  # type: ignore[override]
                return cls([RuntimeToolDescriptor(tool_id="fastp")])

        monkeypatch.setattr("abi.workflow.compiled_plan.ToolCatalog", _Catalog)

        plan_id = bind_confirmed_plan(prepared)
        assert plan_id.startswith("sha256:")
        persisted = load_compiled_plan(outdir / "compiled_plan.json")
        assert persisted.plan_id == plan_id

        # Re-binding an unchanged plan is idempotent and does not rewrite.
        before = (outdir / "compiled_plan.json").read_bytes()
        assert bind_confirmed_plan(prepared) == plan_id
        assert (outdir / "compiled_plan.json").read_bytes() == before

    def test_bind_refuses_drifted_plan(self, tmp_path, monkeypatch) -> None:
        from abi.tool_catalog import RuntimeToolDescriptor

        prepared, outdir = self._prepared(tmp_path)

        class _Catalog(ToolCatalog):
            @classmethod
            def from_project_root(cls):  # type: ignore[override]
                return cls([RuntimeToolDescriptor(tool_id="fastp")])

        monkeypatch.setattr("abi.workflow.compiled_plan.ToolCatalog", _Catalog)
        bind_confirmed_plan(prepared)

        drifted = _exec_plan(
            [
                _plan_step(
                    "s1",
                    outputs={"output_dir": str(outdir / "qc" / "s1")},
                    params={"threads_flag": 8},
                )
            ],
            outdir=str(outdir),
        )
        from types import SimpleNamespace as _NS

        drifted_prepared = _NS(plan=drifted, config={"outdir": str(outdir)})
        with pytest.raises(PlanDriftError, match="drift"):
            bind_confirmed_plan(drifted_prepared)
