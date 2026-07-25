"""Integration tests: every built-in plugin compiles through the plan path.

``ABIAgentInterface.plan()`` compiles each plan into a ``CompiledPlan`` and
persists ``compiled_plan.json``; these tests guard against false positives in
the compiled-plan invariant checks for the shipped plugin declarations.
"""

from __future__ import annotations

import json

import pytest

from abi.agent import ABIAgentInterface

BUILTIN_PLUGINS = [
    "amplicon_16s",
    "easymetagenome",
    "metagenomic_plasmid",
    "metatranscriptomics",
    "rnaseq_expression",
    "viral_viwrap",
    "wgs_bacteria",
]

# Plugins whose declarations require inputs beyond the default config.
EXTRA_KWARGS = {
    "metagenomic_plasmid": {"sample_sheet": "examples/sample_sheet.tsv"},
}


@pytest.mark.parametrize("analysis_type", BUILTIN_PLUGINS)
def test_builtin_plugin_plan_compiles_and_persists(analysis_type, tmp_path):
    outdir = tmp_path / analysis_type / "results"

    payload = json.loads(
        ABIAgentInterface().plan(
            analysis_type=analysis_type,
            outdir=str(outdir),
            log_dir=str(tmp_path / analysis_type / "logs"),
            check_files=False,
            **EXTRA_KWARGS.get(analysis_type, {}),
        )
    )

    assert payload["status"] == "success", payload.get("error")
    compiled_path = outdir / "compiled_plan.json"
    assert compiled_path.exists()
    compiled = json.loads(compiled_path.read_text(encoding="utf-8"))
    assert compiled["schema_version"] == "abi.compiled_plan.v1"
    assert compiled["analysis_type"] == analysis_type
    assert len(compiled["steps"]) == payload["result"]["steps"] > 0
    assert compiled["enabled_steps"] == sorted(step["step_id"] for step in compiled["steps"])
    assert len({step["step_id"] for step in compiled["steps"]}) == len(compiled["steps"])
    step_ids = set(compiled["enabled_steps"])
    for step in compiled["steps"]:
        assert set(step["dependencies"]) <= step_ids
        assert step["execution_kind"] in {"external", "internal_worker", "internal_driver"}
