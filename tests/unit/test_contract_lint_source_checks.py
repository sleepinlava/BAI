"""Unit tests for the source/environment correctness checks in ``contracts.lint``.

Covers the four declaration-correctness checks added on top of the
declaration-coverage gate:

- ``lint_source_keys`` — ``unknown_source_output`` (explicit and template
  sources), ``format_mismatch`` warnings, and ``optional_input_in_template``.
- ``lint_template_input_parity`` — ``unused_registry_input`` warnings.
- ``lint_environment_assignments`` — ``unknown_environment`` errors.
- ``run_contract_lint`` — orchestration wiring of the new checks.
"""

from __future__ import annotations

from abi.contracts.lint import (
    lint_environment_assignments,
    lint_source_keys,
    lint_template_input_parity,
    run_contract_lint,
)


def _dag(nodes):
    return {"nodes": nodes}


def _assembler_node():
    return {
        "id": "assembler",
        "tool_id": "megahit",
        "outputs": {
            "contigs": {"path": "{outdir}/contigs.fa", "format": "fasta"},
            "assembly_graph": {"path": "{outdir}/graph.gfa", "format": "gfa"},
        },
    }


class TestUnknownSourceOutputExplicit:
    def test_unknown_node_is_error(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "blast",
                    "inputs": {"db": {"source": "ghost.contigs"}},
                },
            ]
        )
        findings = lint_source_keys(dag)
        assert len(findings) == 1
        assert findings[0].severity == "error"
        assert findings[0].check == "unknown_source_output"
        assert findings[0].location == "consumer"
        assert "ghost" in findings[0].detail

    def test_undeclared_key_is_error_with_available_keys(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "blast",
                    "inputs": {"db": {"source": "assembler.scaffolds"}},
                },
            ]
        )
        findings = lint_source_keys(dag)
        assert len(findings) == 1
        assert findings[0].check == "unknown_source_output"
        assert "scaffolds" in findings[0].detail
        assert "contigs" in findings[0].detail  # available keys listed

    def test_output_dir_is_always_declared(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "blast",
                    "inputs": {"workdir": {"source": "assembler.output_dir"}},
                },
            ]
        )
        assert lint_source_keys(dag) == []

    def test_valid_explicit_source_is_clean(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "blast",
                    "inputs": {"contigs": {"source": "assembler.contigs"}},
                },
            ]
        )
        assert lint_source_keys(dag) == []

    def test_non_dag_sources_are_skipped(self):
        dag = _dag(
            [
                {
                    "id": "consumer",
                    "tool_id": "blast",
                    "inputs": {
                        "sheet": {"source": "sample_sheet"},
                        "ref": {"source": "config.reference_fasta"},
                        "reads": {"source": "reads"},
                        "dyn1": {"source": "active_assembly.contigs"},
                        "dyn2": {"source": "upstream_qc.reads"},
                    },
                },
            ]
        )
        assert lint_source_keys(dag) == []


class TestUnknownSourceOutputTemplate:
    def test_key_missing_everywhere_is_error(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "scapp",
                    "inputs": {
                        "graph": {"source": "{active_assembly_node}.plasmid_graph"}
                    },
                },
            ]
        )
        findings = lint_source_keys(dag)
        assert len(findings) == 1
        assert findings[0].severity == "error"
        assert findings[0].check == "unknown_source_output"
        assert "plasmid_graph" in findings[0].detail

    def test_partial_coverage_is_clean(self):
        # megahit legitimately lacks assembly_graph; another node provides it.
        dag = _dag(
            [
                {
                    "id": "megahit",
                    "tool_id": "megahit",
                    "outputs": {"contigs": {"path": "{outdir}/c.fa"}},
                },
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "scapp",
                    "inputs": {
                        "graph": {"source": "{active_assembly_node}.assembly_graph"}
                    },
                },
            ]
        )
        assert lint_source_keys(dag) == []

    def test_template_output_dir_is_clean(self):
        dag = _dag(
            [
                {
                    "id": "consumer",
                    "tool_id": "scapp",
                    "inputs": {"workdir": {"source": "{active_qc_node}.output_dir"}},
                },
            ]
        )
        assert lint_source_keys(dag) == []


class TestFormatMismatch:
    def test_differing_formats_warn(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "scapp",
                    "inputs": {
                        "graph": {
                            "source": "assembler.assembly_graph",
                            "format": "fastg",
                        }
                    },
                },
            ]
        )
        findings = lint_source_keys(dag)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].check == "format_mismatch"

    def test_matching_formats_are_clean(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "blast",
                    "inputs": {
                        "contigs": {"source": "assembler.contigs", "format": "fasta"}
                    },
                },
            ]
        )
        assert lint_source_keys(dag) == []

    def test_template_sources_skip_format_check(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "scapp",
                    "inputs": {
                        "graph": {
                            "source": "{active_assembly_node}.assembly_graph",
                            "format": "fastg",
                        }
                    },
                },
            ]
        )
        assert lint_source_keys(dag) == []

    def test_missing_format_on_either_side_is_clean(self):
        dag = _dag(
            [
                {
                    "id": "producer",
                    "tool_id": "x",
                    "outputs": {"result": {"path": "{outdir}/r.txt"}},
                },
                {
                    "id": "consumer",
                    "tool_id": "y",
                    "inputs": {"result": {"source": "producer.result", "format": "txt"}},
                },
            ]
        )
        assert lint_source_keys(dag) == []


class TestOptionalInputInTemplate:
    def _registry(self):
        return {
            "scapp": {
                "id": "scapp",
                "command_template": "scapp -g {graph} -o {outdir} -k {max_kmer}",
            }
        }

    def test_optional_input_in_template_is_error(self):
        dag = _dag(
            [
                {
                    "id": "scapp",
                    "tool_id": "scapp",
                    "inputs": {
                        "graph": {"source": "assembler.assembly_graph"},
                        "max_kmer": {"required": False, "default": "55"},
                    },
                }
            ]
        )
        findings = lint_source_keys(dag, registry_tools=self._registry())
        optional = [f for f in findings if f.check == "optional_input_in_template"]
        assert len(optional) == 1
        assert optional[0].severity == "error"
        assert optional[0].location == "scapp"
        assert "max_kmer" in optional[0].detail

    def test_required_input_in_template_is_clean(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "scapp",
                    "tool_id": "scapp",
                    "inputs": {
                        "graph": {"source": "assembler.assembly_graph"},
                        "max_kmer": {"required": True},
                    },
                },
            ]
        )
        assert lint_source_keys(dag, registry_tools=self._registry()) == []

    def test_optional_input_not_in_template_is_clean(self):
        dag = _dag(
            [
                {
                    "id": "scapp",
                    "tool_id": "scapp",
                    "inputs": {"unused_opt": {"required": False}},
                }
            ]
        )
        assert lint_source_keys(dag, registry_tools=self._registry()) == []

    def test_skipped_without_registry_tools(self):
        dag = _dag(
            [
                {
                    "id": "scapp",
                    "tool_id": "scapp",
                    "inputs": {"max_kmer": {"required": False}},
                }
            ]
        )
        assert lint_source_keys(dag) == []

    def test_unknown_tool_id_is_skipped(self):
        dag = _dag(
            [
                {
                    "id": "internal_agg",
                    "tool_id": "internal",
                    "inputs": {"opt": {"required": False}},
                }
            ]
        )
        assert lint_source_keys(dag, registry_tools=self._registry()) == []


class TestTemplateInputParity:
    def test_unused_declared_input_warns(self):
        registry = {
            "scapp": {
                "id": "scapp",
                "command_template": "scapp -g {graph} -o {outdir}",
                "inputs": ["graph", "assembly"],
            }
        }
        findings = lint_template_input_parity(registry)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].check == "unused_registry_input"
        assert findings[0].location == "scapp"
        assert "assembly" in findings[0].detail

    def test_used_inputs_are_clean(self):
        registry = {
            "scapp": {
                "id": "scapp",
                "command_template": "scapp -g {graph} -o {outdir}",
                "inputs": ["graph"],
            }
        }
        assert lint_template_input_parity(registry) == []

    def test_mapping_input_entries_use_name_or_id(self):
        registry = {
            "tool": {
                "id": "tool",
                "command_template": "run --in {reads}",
                "inputs": [{"name": "reads"}, {"id": "extra"}],
            }
        }
        findings = lint_template_input_parity(registry)
        assert len(findings) == 1
        assert "extra" in findings[0].detail

    def test_tools_without_template_or_inputs_are_skipped(self):
        registry = {
            "no_template": {"id": "no_template", "inputs": ["x"]},
            "no_inputs": {"id": "no_inputs", "command_template": "run {x}"},
        }
        assert lint_template_input_parity(registry) == []


class TestEnvironmentAssignments:
    def test_undefined_env_is_error(self):
        environments = {
            "environments": {"base": {"file": "envs/base.yml"}},
            "tool_assignments": {"plugin": {"scapp": "scapp_env"}},
        }
        findings = lint_environment_assignments(environments)
        assert len(findings) == 1
        assert findings[0].severity == "error"
        assert findings[0].check == "unknown_environment"
        assert findings[0].location == "plugin/scapp"
        assert "scapp_env" in findings[0].detail

    def test_defined_env_is_clean(self):
        environments = {
            "environments": {"base": {}, "scapp": {}},
            "tool_assignments": {"plugin": {"scapp": "scapp", "other": "base"}},
        }
        assert lint_environment_assignments(environments) == []

    def test_missing_assignments_section_is_clean(self):
        assert lint_environment_assignments({"environments": {"base": {}}}) == []

    def test_tools_without_mapping_are_not_reported(self):
        environments = {
            "environments": {"base": {}},
            "tool_assignments": {"plugin": {}},
        }
        assert lint_environment_assignments(environments) == []


class TestRunContractLintWiring:
    def test_source_checks_flow_into_orchestrator(self):
        dag = _dag(
            [
                _assembler_node(),
                {
                    "id": "consumer",
                    "tool_id": "blast",
                    "depends_on": ["assembler"],
                    "inputs": {"db": {"source": "assembler.missing_key"}},
                },
            ]
        )
        result = run_contract_lint(dag)
        checks = {f["check"] for f in result["findings"]}
        assert "unknown_source_output" in checks
        assert result["passed"] is False

    def test_parity_check_runs_with_registry_tools(self):
        result = run_contract_lint(
            _dag([{"id": "only", "tool_id": "x", "depends_on": []}]),
            registry_tools={
                "x": {"id": "x", "command_template": "run {a}", "inputs": ["a", "b"]}
            },
        )
        checks = {f["check"] for f in result["findings"]}
        assert "unused_registry_input" in checks
        assert result["warning_count"] >= 1

    def test_environment_check_runs_only_with_data(self):
        dag = _dag([{"id": "only", "tool_id": "x", "depends_on": []}])
        environments = {
            "environments": {"base": {}},
            "tool_assignments": {"p": {"x": "ghost_env"}},
        }
        with_env = run_contract_lint(dag, environments=environments)
        assert any(f["check"] == "unknown_environment" for f in with_env["findings"])
        without_env = run_contract_lint(dag)
        assert all(f["check"] != "unknown_environment" for f in without_env["findings"])

    def test_optional_input_check_flows_into_orchestrator(self):
        dag = _dag(
            [
                {
                    "id": "scapp",
                    "tool_id": "scapp",
                    "depends_on": [],
                    "inputs": {"max_kmer": {"required": False}},
                }
            ]
        )
        result = run_contract_lint(
            dag,
            registry_tools={
                "scapp": {"id": "scapp", "command_template": "scapp -k {max_kmer}"}
            },
        )
        assert any(f["check"] == "optional_input_in_template" for f in result["findings"])
        assert result["passed"] is False
