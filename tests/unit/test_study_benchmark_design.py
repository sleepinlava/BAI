from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from abi.study.build import _copy_release_inputs

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "experiments" / "abi_control_validation_v1"


def _yaml(name: str) -> dict:
    return yaml.safe_load((STUDY_ROOT / name).read_text(encoding="utf-8"))


def test_release_input_sync_removes_absent_optional_top_level_file(tmp_path: Path) -> None:
    study_root = tmp_path / "study"
    output_root = tmp_path / "release"
    study_root.mkdir()
    output_root.mkdir()
    (study_root / "study.yaml").write_text("status: draft\n", encoding="utf-8")
    stale = output_root / "benchmark_design_zh.md"
    stale.write_text("obsolete release input\n", encoding="utf-8")

    _copy_release_inputs(study_root, output_root)

    assert (output_root / "study.yaml").read_text(encoding="utf-8") == "status: draft\n"
    assert not stale.exists()


def test_benchmark_manifest_materializes_the_preregistered_track_a_design() -> None:
    manifest = _yaml("tasks.yaml")
    tasks = manifest["tasks"]

    assert manifest["task_count"] == 45
    assert len(tasks) == 45
    assert len({task["task_id"] for task in tasks}) == 45

    counts = Counter(task["category"] for task in tasks)
    assert counts == {
        "discovery": 3,
        "planning": 3,
        "preflight": 6,
        "authorization": 6,
        "output_acceptance": 6,
        "recovery": 6,
        "capability_boundary": 3,
        "resource_identity": 3,
        "backend_portability": 3,
        "scope_containment": 3,
        "provenance_report": 3,
    }


def test_core_fault_tasks_have_clean_or_approved_sisters_for_every_workflow() -> None:
    tasks = _yaml("tasks.yaml")["tasks"]
    by_workflow: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for task in tasks:
        by_workflow[task["workflow"]][task["category"]].append(task)

    assert set(by_workflow) == {
        "rnaseq_expression",
        "wgs_bacteria",
        "metagenomic_plasmid",
    }
    for categories in by_workflow.values():
        for category in ["preflight", "output_acceptance", "recovery"]:
            assert {task["variant"] for task in categories[category]} == {"fault", "clean"}
        assert {task["variant"] for task in categories["authorization"]} == {
            "not_approved",
            "approved",
        }


def test_study_declares_all_targeted_ablation_conditions_and_scopes() -> None:
    conditions = _yaml("study.yaml")["conditions"]

    assert set(conditions) == {
        "matched_advisory",
        "abi_full",
        "abi_no_runtime_contracts",
        "abi_no_authorization_gate",
        "abi_no_structured_recovery",
        "abi_no_forced_provenance",
        "direct_general_agent",
    }
    assert conditions["abi_no_runtime_contracts"]["confirmatory_scope"] == [
        "preflight",
        "output_acceptance",
        "resource_identity",
    ]
    assert conditions["abi_no_authorization_gate"]["confirmatory_scope"] == [
        "authorization",
        "scope_containment",
    ]
    assert conditions["abi_no_structured_recovery"]["confirmatory_scope"] == ["recovery"]
    assert conditions["abi_no_forced_provenance"]["confirmatory_scope"] == ["provenance_report"]


def test_track_b_release_manifest_has_three_d1_tasks() -> None:
    external = _yaml("external_tasks/manifest.yaml")

    assert external["task_count"] == 3
    assert {task["task_id"] for task in external["tasks"]} == {
        "bioagent_deseq_clean",
        "core_retrieve_scapp",
        "core_easy_st93",
    }
    assert all(task["modification_level"] == "D1" for task in external["tasks"])
    assert all(task["original_prompt"] for task in external["tasks"])
    assert all(task["adapted_prompt"] for task in external["tasks"])
    assert all(task["prompt_diff"] for task in external["tasks"])
    assert all(task["license"] for task in external["tasks"])
    for task in external["tasks"]:
        source = STUDY_ROOT / "external_tasks" / task["original_prompt"].split("#", 1)[0]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == task["sha256"]
        assert task["freeze_status"].endswith("pending")
