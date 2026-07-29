from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from abi.study.cli import app
from abi.study.harness import invoke_workspace_operation, prepare_trial

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "experiments" / "abi_control_validation_v1"


def test_study_build_artifacts_and_prepare_trial(tmp_path: Path) -> None:
    runner = CliRunner()
    generated = tmp_path / "generated"
    result = runner.invoke(
        app,
        [
            "build-artifacts",
            "--study-root",
            str(STUDY_ROOT),
            "--repo-root",
            str(REPO_ROOT),
            "--out",
            str(generated),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (generated / "contract_snapshot" / "rnaseq_expression.json").is_file()
    assert (generated / "advisory_cards" / "rnaseq_expression.md").is_file()
    assert (generated / "semantic_coverage.tsv").is_file()
    result = runner.invoke(
        app,
        [
            "record-coverage-review",
            "--coverage",
            str(generated / "semantic_coverage.tsv"),
            "--reviewer",
            "independent-test-reviewer",
            "--attest-all-pass",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["rows"] == 51

    trial_root = tmp_path / "trial"
    result = runner.invoke(
        app,
        [
            "run",
            "--study",
            str(STUDY_ROOT / "study.yaml"),
            "--task",
            "rnaseq_t3_missing_mate",
            "--condition",
            "matched_advisory",
            "--model",
            "test-model",
            "--seed",
            "1103",
            "--artifact-root",
            str(trial_root),
            "--tasks",
            str(STUDY_ROOT / "tasks.yaml"),
            "--fixtures",
            str(generated / "fixtures"),
            "--interface-root",
            str(generated),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "prepared"
    assert (trial_root / "request.json").is_file()
    assert (trial_root / "input" / "config.yaml").is_file()
    assert not (trial_root / "input" / "shim_state.json").exists()
    assert (trial_root / "interface" / "advisory_card.md").is_file()
    interface = json.loads(
        (trial_root / "interface" / "interface.json").read_text(encoding="utf-8")
    )
    schemas = json.loads(
        (trial_root / "interface" / "operation_schemas.json").read_text(encoding="utf-8")
    )
    assert "active_preflight_contracts" not in interface
    assert "abi_call" not in schemas
    assert "behavior" not in schemas["execute_tool"]["properties"]
    assert (trial_root / ".study_authority" / "runtime_control.json").is_file()
    result = runner.invoke(
        app,
        [
            "invoke",
            "--trial-root",
            str(trial_root),
            "--operation",
            "list_files",
            "--arguments",
            '{"visible_root": "/task/input"}',
        ],
    )
    assert result.exit_code == 0, result.output
    assert "config.yaml" in json.loads(result.output)["result"]

    response = {
        "terminal_state": "blocked",
        "selected_workflow": "rnaseq_expression",
        "evidence": ["/task/input/reads/D1_control_R2.fastq missing"],
        "blocking_code": "incomplete_pairs",
    }
    (trial_root / "final_response.json").write_text(json.dumps(response), encoding="utf-8")
    (trial_root / "transcript.jsonl").write_text(
        json.dumps({"role": "assistant", "content": response}) + "\n",
        encoding="utf-8",
    )
    (trial_root / "usage.json").write_text(
        json.dumps(
            {
                "wall_seconds": 1,
                "tool_calls": 1,
                "input_tokens": 100,
                "output_tokens": 40,
                "recovery_attempts": 0,
            }
        ),
        encoding="utf-8",
    )
    (trial_root / "work" / "events.jsonl").write_text("", encoding="utf-8")
    (trial_root / "work" / "readiness.json").write_text(
        json.dumps(
            {
                "ready": False,
                "workflow": "rnaseq_expression",
                "evidence": ["/task/input/reads/D1_control_R2.fastq missing"],
                "blocking_code": "incomplete_pairs",
            }
        ),
        encoding="utf-8",
    )
    record = tmp_path / "trial_record.json"
    result = runner.invoke(
        app,
        [
            "grade",
            "--study",
            str(STUDY_ROOT / "study.yaml"),
            "--tasks",
            str(STUDY_ROOT / "tasks.yaml"),
            "--trial-root",
            str(trial_root),
            "--out",
            str(record),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(record.read_text(encoding="utf-8"))["scores"]["cvc"] == 1


def test_runtime_contract_ablation_changes_invalid_output_acceptance(tmp_path: Path) -> None:
    study = yaml.safe_load((STUDY_ROOT / "study.yaml").read_text(encoding="utf-8"))
    tasks = yaml.safe_load((STUDY_ROOT / "tasks.yaml").read_text(encoding="utf-8"))
    trial_roots = {
        condition: tmp_path / condition for condition in ["abi_full", "abi_no_runtime_contracts"]
    }
    for condition, trial_root in trial_roots.items():
        prepare_trial(
            study=study,
            tasks=tasks,
            study_root=STUDY_ROOT,
            fixture_root=STUDY_ROOT / "fixtures",
            interface_root=STUDY_ROOT,
            task_id="rnaseq_t5_empty_count_table",
            condition=condition,
            model_id="primary",
            seed=1103,
            artifact_root=trial_root,
        )

    arguments = {
        "tool_id": "build_count_matrix",
        "config_path": "/task/input/config.yaml",
        "arguments": {
            "count_matrix_script": "/task/input/build_count_matrix.py",
            "expression_dir": "/task/work/expression",
            "sample_sheet": "/task/input/samples.tsv",
        },
        "outputs": {
            "count_matrix": "/task/work/counts.tsv",
            "sample_metadata": "/task/work/metadata.tsv",
            "output_dir": "/task/work/matrix",
        },
    }
    full = invoke_workspace_operation(
        trial_root=trial_roots["abi_full"],
        operation="execute_tool",
        arguments=arguments,
    )
    ablation = invoke_workspace_operation(
        trial_root=trial_roots["abi_no_runtime_contracts"],
        operation="execute_tool",
        arguments=arguments,
    )

    assert full["status"] == "contract_violation", full
    assert full["contract_errors"] == ["count_matrix:empty_file"]
    assert ablation["status"] == "success"
    assert not (trial_roots["abi_full"] / "input" / "shim_state.json").exists()
    schemas = json.loads(
        (trial_roots["abi_full"] / "interface" / "operation_schemas.json").read_text(
            encoding="utf-8"
        )
    )
    assert "behavior" not in schemas["execute_tool"]["properties"]
