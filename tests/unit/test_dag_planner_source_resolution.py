"""Plan-time validation of DAG input source resolution (abi.dag_planner).

Regression tests for the silent-empty source bug: a downstream node declaring
``source: '{active_assembly_node}.assembly_graph'`` (or an explicit
``NODE.KEY`` source) whose key no upstream node can provide used to resolve to
``""`` at plan time and only fail mid-execution inside the tool.  These tests
pin the new plan-time ``ValueError`` semantics and the escape hatches
(``fallback`` / ``default`` / ``required: false``).
"""

from __future__ import annotations

import pytest

from abi.dag_planner import (
    UniversalDAG,
    _resolve_cross_sample_inputs,
    _resolve_inputs,
    build_plan_from_dag,
)
from abi.schemas import SampleContext, SampleInput

# ── Helpers ────────────────────────────────────────────────────────────────

_SAMPLE = SampleInput(sample_id="S1", platform="illumina", read1="R1.fq", read2="R2.fq")


def _make_dag(scapp_inputs: dict, *, declare_graph: bool = False) -> UniversalDAG:
    """Two-node DAG: an assembler feeding a scapp-like binning node."""
    assembler_outputs = {"assembly": {"type": "file", "path": "{outdir}/asm/{sample_id}/a.fasta"}}
    if declare_graph:
        assembler_outputs["assembly_graph"] = {
            "type": "file",
            "path": "{outdir}/asm/{sample_id}/a.fastg",
        }
    spec = {
        "pipeline_id": "test_pipeline",
        "platforms": ["illumina"],
        "category_dirs": {"assembly": "02_assembly", "binning": "03_binning"},
        "nodes": {
            "assembly_megahit": {
                "tool_id": "megahit",
                "category": "assembly",
                "platforms": ["illumina"],
                "outputs": assembler_outputs,
            },
            "plasmid_binning_scapp": {
                "tool_id": "scapp",
                "category": "binning",
                "platforms": ["illumina"],
                "depends_on": ["assembly_megahit"],
                "inputs": scapp_inputs,
            },
        },
    }
    return UniversalDAG(spec)


def _upstream_outputs(*, graph: str | None = None) -> dict:
    """Resolved outputs of the assembler, as populated by the plan loop."""
    outputs = {
        "assembly": "/results/02_assembly/S1/a.fasta",
        "output_dir": "/results/02_assembly/S1",
    }
    if graph is not None:
        outputs["assembly_graph"] = graph
    return {"assembly_megahit": outputs}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Explicit NODE.KEY sources
# ═══════════════════════════════════════════════════════════════════════════


class TestExplicitSource:
    def test_undeclared_output_key_raises_plan_error(self):
        dag = _make_dag(
            {"assembly_graph": {"type": "file", "source": "assembly_megahit.assembly_graph"}}
        )
        with pytest.raises(ValueError) as excinfo:
            _resolve_inputs(dag, "plasmid_binning_scapp", _SAMPLE, {}, _upstream_outputs(), None)
        msg = str(excinfo.value)
        assert "'plasmid_binning_scapp'" in msg  # consuming node
        assert "'assembly_graph'" in msg  # input key and bad output key
        assert "assembly_megahit" in msg  # upstream node
        assert "assembly" in msg  # available output keys listed

    def test_declared_key_with_empty_value_still_uses_default(self):
        """A declared key whose runtime value is empty is not a static bug."""
        dag = _make_dag(
            {
                "assembly_graph": {
                    "type": "file",
                    "source": "assembly_megahit.assembly_graph",
                    "default": "/defaults/graph.fastg",
                }
            },
            declare_graph=True,
        )
        resolved = _resolve_inputs(
            dag,
            "plasmid_binning_scapp",
            _SAMPLE,
            {},
            _upstream_outputs(graph=""),
            None,
        )
        assert resolved["assembly_graph"] == "/defaults/graph.fastg"

    def test_declared_key_resolves_happy_path(self):
        dag = _make_dag(
            {"assembly_graph": {"type": "file", "source": "assembly_megahit.assembly_graph"}},
            declare_graph=True,
        )
        resolved = _resolve_inputs(
            dag,
            "plasmid_binning_scapp",
            _SAMPLE,
            {},
            _upstream_outputs(graph="/results/02_assembly/S1/a.fastg"),
            None,
        )
        assert resolved["assembly_graph"] == "/results/02_assembly/S1/a.fastg"

    def test_unknown_upstream_node_keeps_legacy_empty_behavior(self):
        """Sources naming nodes absent from the DAG are out of scope."""
        dag = _make_dag({"x": {"type": "file", "source": "no_such_node.whatever"}})
        resolved = _resolve_inputs(
            dag, "plasmid_binning_scapp", _SAMPLE, {}, _upstream_outputs(), None
        )
        assert resolved["x"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# 2. Template {...}.KEY sources
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateSource:
    def test_unresolvable_required_input_raises_plan_error(self):
        dag = _make_dag(
            {
                "assembly_graph": {
                    "type": "file",
                    "source": "{active_assembly_node}.assembly_graph",
                }
            }
        )
        with pytest.raises(ValueError) as excinfo:
            _resolve_inputs(dag, "plasmid_binning_scapp", _SAMPLE, {}, _upstream_outputs(), None)
        msg = str(excinfo.value)
        assert "'plasmid_binning_scapp'" in msg
        assert "'assembly_graph'" in msg
        assert "Scanned upstream nodes" in msg
        assert "assembly_megahit" in msg  # scanned node listed with its keys

    def test_unresolvable_required_false_allows_empty(self):
        dag = _make_dag(
            {
                "assembly_graph": {
                    "type": "file",
                    "source": "{active_assembly_node}.assembly_graph",
                    "required": False,
                }
            }
        )
        resolved = _resolve_inputs(
            dag, "plasmid_binning_scapp", _SAMPLE, {}, _upstream_outputs(), None
        )
        assert resolved["assembly_graph"] == ""

    def test_unresolvable_rescued_by_fallback(self):
        dag = _make_dag(
            {
                "assembly_graph": {
                    "type": "file",
                    "source": "{active_assembly_node}.assembly_graph",
                    "fallback": "assembly_megahit.assembly",
                }
            }
        )
        resolved = _resolve_inputs(
            dag, "plasmid_binning_scapp", _SAMPLE, {}, _upstream_outputs(), None
        )
        assert resolved["assembly_graph"] == "/results/02_assembly/S1/a.fasta"

    def test_unresolvable_rescued_by_default(self):
        dag = _make_dag(
            {
                "assembly_graph": {
                    "type": "file",
                    "source": "{active_assembly_node}.assembly_graph",
                    "default": "/defaults/graph.fastg",
                }
            }
        )
        resolved = _resolve_inputs(
            dag, "plasmid_binning_scapp", _SAMPLE, {}, _upstream_outputs(), None
        )
        assert resolved["assembly_graph"] == "/defaults/graph.fastg"

    def test_scanned_node_declaring_key_with_empty_value_is_not_static_bug(self):
        """Declared-but-empty runtime values keep the fallback/default chain."""
        dag = _make_dag(
            {
                "assembly_graph": {
                    "type": "file",
                    "source": "{active_assembly_node}.assembly_graph",
                }
            },
            declare_graph=True,
        )
        # The scanned upstream declares the key but resolved it to "".
        resolved = _resolve_inputs(
            dag,
            "plasmid_binning_scapp",
            _SAMPLE,
            {},
            _upstream_outputs(graph=""),
            None,
        )
        assert resolved["assembly_graph"] == ""

    def test_template_resolves_from_offering_upstream(self):
        dag = _make_dag(
            {
                "assembly_graph": {
                    "type": "file",
                    "source": "{active_assembly_node}.assembly_graph",
                }
            },
            declare_graph=True,
        )
        resolved = _resolve_inputs(
            dag,
            "plasmid_binning_scapp",
            _SAMPLE,
            {},
            _upstream_outputs(graph="/results/02_assembly/S1/a.fastg"),
            None,
        )
        assert resolved["assembly_graph"] == "/results/02_assembly/S1/a.fastg"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Cross-sample resolution
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossSampleSource:
    def _make_cross_dag(self) -> UniversalDAG:
        spec = {
            "pipeline_id": "test_pipeline",
            "platforms": ["illumina"],
            "nodes": {
                "assembly_megahit": {
                    "tool_id": "megahit",
                    "category": "assembly",
                    "platforms": ["illumina"],
                    "outputs": {"assembly": {"type": "file"}},
                },
                "report": {
                    "tool_id": "internal",
                    "category": "reporting",
                    "scope": "cross_sample",
                    "platforms": ["illumina"],
                    "depends_on": ["assembly_megahit"],
                    "inputs": {
                        "graph": {"type": "file", "source": "assembly_megahit.assembly_graph"}
                    },
                },
            },
        }
        return UniversalDAG(spec)

    def test_cross_sample_undeclared_key_raises_plan_error(self):
        dag = self._make_cross_dag()
        ctx = SampleContext(samples=[_SAMPLE], multi_sample=False, has_groups=False)
        with pytest.raises(ValueError, match="assembly_graph"):
            _resolve_cross_sample_inputs(
                dag,
                "report",
                ctx,
                {},
                {"S1": {"assembly_megahit": {"assembly": "/a.fasta"}}},
                {},
                None,
            )


# ═══════════════════════════════════════════════════════════════════════════
# 4. End-to-end via build_plan_from_dag
# ═══════════════════════════════════════════════════════════════════════════


def test_build_plan_fails_at_plan_time_for_unresolvable_template_source(tmp_path):
    dag_path = tmp_path / "pipeline_dag.yaml"
    dag_path.write_text(
        "\n".join(
            [
                "pipeline_id: test_pipeline",
                "platforms: [illumina]",
                "category_dirs: {assembly: 02_assembly, binning: 03_binning}",
                "nodes:",
                "  assembly_megahit:",
                "    tool_id: megahit",
                "    category: assembly",
                "    platforms: [illumina]",
                "    outputs:",
                "      assembly: {type: file, path: '{outdir}/02_assembly/{sample_id}/a.fasta'}",
                "  plasmid_binning_scapp:",
                "    tool_id: scapp",
                "    category: binning",
                "    platforms: [illumina]",
                "    depends_on: [assembly_megahit]",
                "    inputs:",
                "      assembly_graph:",
                "        type: file",
                "        source: '{active_assembly_node}.assembly_graph'",
            ]
        )
    )
    config = {"outdir": str(tmp_path / "results")}
    ctx = SampleContext(samples=[_SAMPLE], multi_sample=False, has_groups=False)
    with pytest.raises(ValueError, match="no active upstream node offers output"):
        build_plan_from_dag(dag_path, config, ctx)


def test_build_plan_happy_path_unchanged(tmp_path):
    dag_path = tmp_path / "pipeline_dag.yaml"
    dag_path.write_text(
        "\n".join(
            [
                "pipeline_id: test_pipeline",
                "platforms: [illumina]",
                "category_dirs: {assembly: 02_assembly, binning: 03_binning}",
                "nodes:",
                "  assembly_megahit:",
                "    tool_id: megahit",
                "    category: assembly",
                "    platforms: [illumina]",
                "    outputs:",
                "      assembly: {type: file, path: '{outdir}/02_assembly/{sample_id}/a.fasta'}",
                "      assembly_graph:",
                "        type: file",
                "        path: '{outdir}/02_assembly/{sample_id}/a.fastg'",
                "  plasmid_binning_scapp:",
                "    tool_id: scapp",
                "    category: binning",
                "    platforms: [illumina]",
                "    depends_on: [assembly_megahit]",
                "    inputs:",
                "      assembly: {type: file, source: '{active_assembly_node}.assembly'}",
                "      assembly_graph:",
                "        type: file",
                "        source: '{active_assembly_node}.assembly_graph'",
            ]
        )
    )
    config = {"outdir": str(tmp_path / "results")}
    ctx = SampleContext(samples=[_SAMPLE], multi_sample=False, has_groups=False)
    plan = build_plan_from_dag(dag_path, config, ctx)
    scapp_step = next(s for s in plan.steps if s.tool_id == "scapp")
    assert scapp_step.inputs["assembly"].endswith("02_assembly/S1/a.fasta")
    assert scapp_step.inputs["assembly_graph"].endswith("02_assembly/S1/a.fastg")
