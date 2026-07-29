from __future__ import annotations

import json
from pathlib import Path

import yaml

from abi.study.grading import grade_trial

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "experiments" / "abi_control_validation_v1"


def test_grader_computes_controlled_valid_completion_from_files_and_events(
    tmp_path: Path,
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    response = {
        "terminal_state": "blocked",
        "selected_workflow": "rnaseq_expression",
        "evidence": ["/task/input/samples.tsv"],
        "blocking_code": "incomplete_pairs",
    }
    (tmp_path / "final_response.json").write_text(json.dumps(response), encoding="utf-8")
    (work / "readiness.json").write_text(
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
    (work / "events.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "transcript.jsonl").write_text(
        json.dumps({"role": "assistant", "content": response}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "usage.json").write_text(
        json.dumps(
            {
                "wall_seconds": 2.0,
                "tool_calls": 2,
                "input_tokens": 100,
                "output_tokens": 50,
                "recovery_attempts": 0,
            }
        ),
        encoding="utf-8",
    )
    request = {
        "task_id": "rnaseq_t3_missing_mate",
        "condition": "abi_full",
        "model_id": "test-model",
        "seed": 1103,
    }
    (tmp_path / "request.json").write_text(json.dumps(request), encoding="utf-8")

    record = grade_trial(
        study=yaml.safe_load((STUDY_ROOT / "study.yaml").read_text(encoding="utf-8")),
        tasks=yaml.safe_load((STUDY_ROOT / "tasks.yaml").read_text(encoding="utf-8")),
        trial_root=tmp_path,
    )

    assert record["scores"]["cvc"] == 1
    assert record["scores"]["pre_execution_fault_detection"] == 1
    assert record["scores"]["root_cause_accuracy"] == 1
    assert record["scores"]["external_tool_calls_before_block"] == 0
