"""Unit tests for the output-contract exemption mechanism and the
output-contract coverage lint gate (Phase 3).

Runtime: ``validate_output_contract`` skips outputs whose contract mapping
declares ``exempt: true``.  All three runtime call sites
(``executor.py`` external-step path, ``executor.py`` resume path, and
``step_runner.py``) delegate to this one function, so covering it covers
every call site.

Static: ``lint_output_contracts`` requires every external tool node to
declare a non-exempt output contract and validates ``exempt`` usage.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from abi.contracts.lint import lint_output_contracts, run_contract_lint
from abi.contracts.step_contract import validate_output_contract

# ═══════════════════════════════════════════════════════════════════════════
# Runtime: exempt outputs skip validation
# ═══════════════════════════════════════════════════════════════════════════


class TestExemptRuntimeSkip:
    def test_exempt_missing_output_passes(self, tmp_path):
        """An exempt output is skipped even when the file does not exist."""
        contract_spec = {
            "summary": {
                "path": str(tmp_path / "summary.json"),
                "contract": {"exempt": True, "reason": "aggregation node, no file output"},
            }
        }
        outputs = {"summary": str(tmp_path / "summary.json")}
        result = validate_output_contract("step1", outputs, contract_spec)
        assert result.passed is True
        assert result.violations == []
        assert result.checksums == {}

    def test_exempt_existing_output_not_checksummed(self, tmp_path):
        """Exempt outputs skip the checksum recording branch too."""
        real = tmp_path / "real.txt"
        real.write_text("data")
        contract_spec = {
            "real": {"contract": {"exempt": True, "reason": "no file contract"}},
        }
        result = validate_output_contract("step1", {"real": str(real)}, contract_spec)
        assert result.passed is True
        assert result.checksums == {}

    def test_non_exempt_contract_unchanged(self, tmp_path):
        """Contracts without ``exempt`` behave exactly as before."""
        contract_spec = {
            "report": {
                "path": str(tmp_path / "report.html"),
                "contract": {"min_size": "1KB"},
            }
        }
        outputs = {"report": str(tmp_path / "report.html")}
        result = validate_output_contract("step1", outputs, contract_spec)
        assert result.passed is False
        assert [v.check for v in result.violations] == ["file_exists"]

    def test_exempt_false_still_enforced(self, tmp_path):
        """``exempt: false`` is not an exemption."""
        contract_spec = {
            "report": {
                "path": str(tmp_path / "report.html"),
                "contract": {"exempt": False},
            }
        }
        outputs = {"report": str(tmp_path / "report.html")}
        result = validate_output_contract("step1", outputs, contract_spec)
        assert result.passed is False
        assert [v.check for v in result.violations] == ["file_exists"]

    def test_mixed_exempt_and_enforced_outputs(self, tmp_path):
        """Only the exempt output is skipped; sibling outputs are enforced."""
        real = tmp_path / "real.txt"
        real.write_text("x" * 2048)
        contract_spec = {
            "marker": {"contract": {"exempt": True, "reason": "marker only"}},
            "real": {"contract": {"min_size": "1KB"}},
        }
        outputs = {"marker": str(tmp_path / "missing.txt"), "real": str(real)}
        result = validate_output_contract("step1", outputs, contract_spec)
        assert result.passed is True
        assert str(real) in result.checksums


# ═══════════════════════════════════════════════════════════════════════════
# Lint: coverage gate and exempt usage validation
# ═══════════════════════════════════════════════════════════════════════════


def _checks(findings):
    return sorted(f.check for f in findings)


class TestLintOutputContracts:
    def test_external_node_without_contract_fails(self):
        dag = {"nodes": [{"id": "fastp", "tool_id": "fastp", "outputs": {"out": {}}}]}
        findings = lint_output_contracts(dag)
        assert _checks(findings) == ["missing_output_contract"]
        assert findings[0].severity == "error"
        assert findings[0].location == "fastp"

    def test_external_node_without_any_outputs_fails(self):
        dag = {"nodes": [{"id": "fastp", "tool_id": "fastp"}]}
        findings = lint_output_contracts(dag)
        assert _checks(findings) == ["missing_output_contract"]

    def test_external_node_with_contract_passes(self):
        dag = {
            "nodes": [
                {
                    "id": "fastp",
                    "tool_id": "fastp",
                    "outputs": {"out": {"contract": {"min_size": "1KB"}}},
                }
            ]
        }
        assert lint_output_contracts(dag) == []

    def test_external_node_with_only_exempt_contract_fails(self):
        """An exempt-only external node still has no *enforced* contract."""
        dag = {
            "nodes": [
                {
                    "id": "fastp",
                    "tool_id": "fastp",
                    "outputs": {"out": {"contract": {"exempt": True, "reason": "r"}}},
                }
            ]
        }
        findings = lint_output_contracts(dag)
        assert _checks(findings) == ["missing_output_contract"]

    def test_internal_nodes_not_required_to_declare(self):
        """Internal/aggregation nodes are exempt from the coverage rule."""
        dag = {
            "nodes": [
                {"id": "agg_a", "tool_id": "internal"},
                {"id": "agg_b", "tool_id": "x", "internal_handler": "merge_tables"},
                {
                    "id": "agg_c",
                    "tool_id": "y",
                    "params": {"_internal_handler": {"handler_id": "collect"}},
                },
            ]
        }
        assert lint_output_contracts(dag) == []

    def test_dict_format_nodes_supported(self):
        dag = {
            "nodes": {
                "fastp": {"tool_id": "fastp", "outputs": {"out": {}}},
                "agg": {"tool_id": "internal"},
            }
        }
        findings = lint_output_contracts(dag)
        assert _checks(findings) == ["missing_output_contract"]
        assert findings[0].location == "fastp"

    def test_exempt_without_reason_fails(self):
        dag = {
            "nodes": [
                {
                    "id": "agg",
                    "tool_id": "internal",
                    "outputs": {"out": {"contract": {"exempt": True}}},
                }
            ]
        }
        findings = lint_output_contracts(dag)
        assert _checks(findings) == ["exempt_missing_reason"]

    def test_exempt_with_blank_reason_fails(self):
        dag = {
            "nodes": [
                {
                    "id": "agg",
                    "tool_id": "internal",
                    "outputs": {"out": {"contract": {"exempt": True, "reason": "   "}}},
                }
            ]
        }
        findings = lint_output_contracts(dag)
        assert _checks(findings) == ["exempt_missing_reason"]

    def test_exempt_mixed_with_check_keys_fails(self):
        dag = {
            "nodes": [
                {
                    "id": "agg",
                    "tool_id": "internal",
                    "outputs": {
                        "out": {
                            "contract": {
                                "exempt": True,
                                "reason": "aggregation",
                                "min_size": "1KB",
                                "extensions": [".txt"],
                            }
                        }
                    },
                }
            ]
        }
        findings = lint_output_contracts(dag)
        assert _checks(findings) == ["exempt_mixed_with_checks"]
        assert "min_size" in findings[0].detail

    def test_wellformed_exempt_passes(self):
        dag = {
            "nodes": [
                {
                    "id": "agg",
                    "tool_id": "internal",
                    "outputs": {"out": {"contract": {"exempt": True, "reason": "no file output"}}},
                }
            ]
        }
        assert lint_output_contracts(dag) == []


# ═══════════════════════════════════════════════════════════════════════════
# run_contract_lint wiring
# ═══════════════════════════════════════════════════════════════════════════


class TestRunContractLintGate:
    _UNCOVERED_DAG = {"nodes": [{"id": "fastp", "tool_id": "fastp"}]}

    def test_gate_off_by_default(self):
        """Programmatic callers stay lenient unless they opt in."""
        result = run_contract_lint(self._UNCOVERED_DAG)
        assert result["passed"] is True
        assert not any(f["check"] == "missing_output_contract" for f in result["findings"])

    def test_gate_on_flags_uncovered_node(self):
        result = run_contract_lint(self._UNCOVERED_DAG, enforce_output_contract_coverage=True)
        assert result["passed"] is False
        assert any(f["check"] == "missing_output_contract" for f in result["findings"])

    def test_fully_declared_plugin_passes(self, tmp_path):
        """A fake plugin with contracts, a well-formed exempt node, and a
        limitations declaration passes the full gated lint."""
        dag = {
            "nodes": {
                "fastp": {
                    "tool_id": "fastp",
                    "depends_on": [],
                    "outputs": {
                        "clean_r1": {
                            "path": "{outdir}/clean.fq.gz",
                            "contract": {"min_size": "1KB", "extensions": [".gz"]},
                        }
                    },
                },
                "aggregate": {
                    "tool_id": "internal",
                    "depends_on": ["fastp"],
                    "outputs": {
                        "summary": {
                            "contract": {
                                "exempt": True,
                                "reason": "cross-sample aggregation, no file output",
                            }
                        }
                    },
                },
            }
        }
        (tmp_path / "pipeline_dag.yaml").write_text(yaml.safe_dump(dag), encoding="utf-8")
        (tmp_path / "limitations.yaml").write_text(
            "limitations:\n  - Declared limitation.\n", encoding="utf-8"
        )
        result = run_contract_lint(dag, plugin_root=tmp_path, enforce_output_contract_coverage=True)
        assert result["passed"] is True
        assert result["error_count"] == 0
